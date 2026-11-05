"""Fetch Yahoo data, score a configurable universe, and export an auditable workbook."""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

from .core import Record, STARTER_TICKERS, rank

LOG = logging.getLogger(__name__)


def load_universe(path: Path) -> list[str]:
    symbols = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        symbol = line.split('#', 1)[0].strip().upper()
        if not symbol or symbol == 'TICKER':
            continue
        if symbol.endswith('.SW'):
            symbol = symbol[:-3]
        if not symbol.isalnum():
            raise ValueError(f'Invalid Swiss ticker: {symbol!r}')
        symbols.append(symbol)
    if not symbols or len(symbols) != len(set(symbols)):
        raise ValueError('Universe file must contain unique, non-empty ticker symbols')
    return symbols


def fetch(symbol: str) -> Record:
    import yfinance as yf

    ticker = yf.Ticker(f'{symbol}.SW')
    info = {}
    closes = []
    dates = []
    errors = []
    try:
        info = ticker.info or {}
    except Exception as exc:
        errors.append(f'fundamentals: {type(exc).__name__}: {exc}')
    try:
        history = ticker.history(period='2y', interval='1d', auto_adjust=True, timeout=20)
        if not history.empty and 'Close' in history:
            series = history['Close'].dropna()
            closes = [float(v) for v in series.tolist()]
            dates = [d.to_pydatetime() for d in series.index]
    except Exception as exc:
        errors.append(f'prices: {type(exc).__name__}: {exc}')
    return Record(symbol, info, closes, dates, '; '.join(errors))


def export(rows: list[dict], path: Path, asof: datetime) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    columns = ['rank', 'ticker', 'yahoo_symbol', 'company', 'sector', 'financial',
               'last_close', 'price_date', 'currency', 'fundamental', 'fundamental_coverage',
               'factor', 'factor_coverage', 'technical', 'technical_coverage', 'total', 'status', 'issues']
    for sheet, data in [(wb.active, rows), (wb.create_sheet('Top 10'), [r for r in rows if r['rank'] is not None][:10])]:
        sheet.title = 'Ranking' if sheet == wb.active else 'Top 10'
        sheet.append(columns)
        for row in data:
            sheet.append([row.get(k) for k in columns])
        sheet.freeze_panes = 'C2'
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(color='FFFFFF', bold=True)
            cell.fill = PatternFill('solid', fgColor='17365D')
        for idx, name in enumerate(columns, 1):
            sheet.column_dimensions[get_column_letter(idx)].width = min(65, max(12, len(name) + 3))
        for row in sheet.iter_rows(min_row=2):
            for col in (10, 12, 14, 16):
                row[col-1].number_format = '0.0'
    meta = wb.create_sheet('Methodology')
    for line in [
        ('As of UTC', asof.isoformat()), ('Universe', ', '.join(r['ticker'] for r in rows)),
        ('Weights', 'Fundamental 40%; Factor 35%; Technical 25%'),
        ('Scores', 'Each observed metric maps linearly to 0–100 between documented bounds; observed metrics average within a pillar.'),
        ('Fundamental', 'ROE 0–25%; earnings growth -20–25%; revenue growth -10–20%; operating margin 0–30%; debt/equity 0–200 (lower better).'),
        ('Financials', 'UBSG, ZURN, SREN, SLHN and Yahoo Financial Services: profit margin 0–30% replaces operating margin and debt/equity is omitted.'),
        ('Factor', 'Forward P/E 5–35; P/B 0.5–8; dividend yield 0–6%; EV/EBITDA 4–25 only for non-financials. Valuation ratios must be positive.'),
        ('Technical', '126-session return -30–40%; close relative to 200-day simple average -20–20%.'),
        ('Eligibility', 'All 3 pillars need at least one valid metric; price history needs 200 positive daily closes and last close <=10 days old.'),
        ('Missing data', 'No imputation. Missing metrics listed in Ranking; partial pillar averages use observed metrics only.'),
        ('Source', 'Yahoo Finance via yfinance; adjusted daily closing prices; point-in-time fundamentals unavailable.'),
    ]:
        meta.append(line)
    meta.column_dimensions['A'].width = 20
    meta.column_dimensions['B'].width = 125
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description='Swiss equity screener')
    parser.add_argument('--output', type=Path, default=Path('output/bendio_screener.xlsx'))
    parser.add_argument('--universe', type=Path, default=Path('universe.txt'), help='One Swiss ticker per line; default: universe.txt')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    records = []
    symbols = load_universe(args.universe)
    for symbol in symbols:
        LOG.info('Fetching %s.SW', symbol)
        records.append(fetch(symbol))
    asof = datetime.now(timezone.utc)
    rows = rank(records, asof)
    export(rows, args.output, asof)
    LOG.info('Saved %s; %s/%s ranked', args.output, sum(r['rank'] is not None for r in rows), len(rows))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
