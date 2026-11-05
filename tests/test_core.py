import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone

from bendio_screener.cli import load_universe
from bendio_screener.core import FINANCIAL, Record, STARTER_TICKERS, number, rank, score

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)


def sample(symbol, info=None, prices=None):
    info = info if info is not None else {
        'returnOnEquity': .15, 'earningsGrowth': .1, 'revenueGrowth': .08,
        'operatingMargins': .2, 'debtToEquity': 70, 'profitMargins': .18,
        'forwardPE': 17, 'priceToBook': 2, 'dividendYield': .03,
        'enterpriseToEbitda': 12,
    }
    prices = prices if prices is not None else [100 + i * .1 for i in range(220)]
    dates = [NOW - timedelta(days=219-i) for i in range(len(prices))]
    return Record(symbol, info, prices, dates)


class ScoringTests(unittest.TestCase):
    def test_universe_exact(self):
        self.assertEqual(len(STARTER_TICKERS), 23)
        self.assertEqual(len(set(STARTER_TICKERS)), 23)
        self.assertEqual(set(FINANCIAL), {'UBSG', 'ZURN', 'SREN', 'SLHN'})

    def test_all_ranked_and_sorted(self):
        rows = rank([sample(s) for s in STARTER_TICKERS], NOW)
        self.assertEqual([r['rank'] for r in rows], list(range(1, 24)))
        self.assertEqual(len(rows[:10]), 10)
        self.assertTrue(all(r['total'] is not None for r in rows))

    def test_missing_pillar_unranked(self):
        record = sample('RO', info={})
        result = score(record, NOW)
        self.assertIsNone(result['total'])
        self.assertEqual(result['status'], 'unranked')
        self.assertIn('missing scoring pillar', result['issues'])

    def test_financial_excludes_operating_debt_and_ev(self):
        result = score(sample('UBSG'), NOW)
        self.assertEqual(result['fundamental_coverage'], '4/4')
        self.assertEqual(result['factor_coverage'], '3/3')

    def test_stale_or_short_prices_unranked(self):
        old = sample('RO')
        old.dates = [d - timedelta(days=20) for d in old.dates]
        self.assertIsNone(score(old, NOW)['total'])
        self.assertIsNone(score(sample('RO', prices=[100] * 50), NOW)['total'])

    def test_invalid_values_and_coverage(self):
        self.assertIsNone(number(float('nan')))
        self.assertIsNone(number(True))
        record = sample('RO')
        record.info['forwardPE'] = -4
        result = score(record, NOW)
        self.assertEqual(result['factor_coverage'], '3/4')
        self.assertIn('forward_pe', result['issues'])

    def test_universe_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'universe.txt'
            path.write_text('ticker\nRO.SW\n NOVN # comment\n', encoding='utf-8')
            self.assertEqual(load_universe(path), ['RO', 'NOVN'])
            path.write_text('RO\nRO.SW\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_universe(path)

    def test_coverage_validation(self):
        self.assertEqual(len(rank([sample('RO'), sample('NOVN')], NOW)), 2)
        with self.assertRaises(ValueError):
            rank([], NOW)
        with self.assertRaises(ValueError):
            rank([sample(s) for s in STARTER_TICKERS] + [sample('RO')], NOW)


if __name__ == '__main__':
    unittest.main()
