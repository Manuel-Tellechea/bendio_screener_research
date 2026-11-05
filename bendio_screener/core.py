"""Transparent, coverage-aware Swiss equity scoring."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

STARTER_TICKERS = 'RO NOVN NESN ABBN UBSG CFR ZURN GALD LONN SREN HOLN GIVN SCMN SDZ SCHN ALC SIKA KNIN SLHN HBAN SGSN LISN EMSN'.split()
WEIGHTS = {'fundamental': .40, 'factor': .35, 'technical': .25}
FINANCIAL = {'UBSG', 'ZURN', 'SREN', 'SLHN'}


@dataclass
class Record:
    ticker: str
    info: dict[str, Any]
    closes: list[float]
    dates: list[datetime]
    error: str = ''


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def bounded(value: float, low: float, high: float, higher: bool = True) -> float:
    result = 100 * (value - low) / (high - low)
    return max(0., min(100., result if higher else 100 - result))


def metric(info: dict, key: str, low: float, high: float, higher: bool = True,
           positive: bool = False) -> float | None:
    value = number(info.get(key))
    if value is None or (positive and value <= 0):
        return None
    return bounded(value, low, high, higher)


def mean_available(values: dict[str, float | None]) -> tuple[float | None, str, str]:
    present = {key: val for key, val in values.items() if val is not None}
    missing = sorted(set(values) - set(present))
    score = sum(present.values()) / len(present) if present else None
    return score, f'{len(present)}/{len(values)}', ', '.join(missing)


def score(record: Record, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    symbol = record.ticker
    info = record.info or {}
    financial = symbol in FINANCIAL or info.get('sector') == 'Financial Services'
    fundamental_metrics = {
        'roe': metric(info, 'returnOnEquity', 0, .25),
        'earnings_growth': metric(info, 'earningsGrowth', -.20, .25),
        'revenue_growth': metric(info, 'revenueGrowth', -.10, .20),
    }
    if financial:
        fundamental_metrics['profit_margin'] = metric(info, 'profitMargins', 0, .30)
    else:
        fundamental_metrics['operating_margin'] = metric(info, 'operatingMargins', 0, .30)
        fundamental_metrics['debt_to_equity'] = metric(info, 'debtToEquity', 0, 200, False)
    factor_metrics = {
        'forward_pe': metric(info, 'forwardPE', 5, 35, False, True),
        'price_to_book': metric(info, 'priceToBook', .5, 8, False, True),
        'dividend_yield': metric(info, 'dividendYield', 0, .06),
    }
    if not financial:
        factor_metrics['ev_to_ebitda'] = metric(info, 'enterpriseToEbitda', 4, 25, False, True)
    closes = record.closes
    valid_prices = len(closes) >= 200 and len(closes) == len(record.dates) and all(
        number(v) is not None and v > 0 for v in closes)
    fresh = False
    if valid_prices:
        last = record.dates[-1]
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        fresh = 0 <= (now - last).days <= 10
    technical_metrics: dict[str, float | None] = {'six_month_momentum': None, 'above_200d': None}
    if valid_prices and fresh:
        technical_metrics = {
            'six_month_momentum': bounded(closes[-1] / closes[-127] - 1, -.30, .40),
            'above_200d': bounded(closes[-1] / (sum(closes[-200:]) / 200) - 1, -.20, .20),
        }
    groups = {'fundamental': mean_available(fundamental_metrics),
              'factor': mean_available(factor_metrics),
              'technical': mean_available(technical_metrics)}
    # Require evidence in every pillar; never boost a stock by dropping a pillar.
    complete = all(groups[name][0] is not None for name in WEIGHTS)
    total = sum(WEIGHTS[name] * groups[name][0] for name in WEIGHTS) if complete else None
    issues = [record.error] if record.error else []
    if not valid_prices:
        issues.append('insufficient/invalid price history (need 200 daily closes)')
    elif not fresh:
        issues.append('stale price history (>10 days)')
    for name, (_, _, missing) in groups.items():
        if missing:
            issues.append(f'{name} missing: {missing}')
    if not complete:
        issues.append('unranked: missing scoring pillar')
    return {
        'ticker': symbol, 'yahoo_symbol': f'{symbol}.SW', 'company': info.get('shortName') or '',
        'sector': info.get('sector') or '', 'financial': financial,
        'last_close': closes[-1] if valid_prices else None,
        'price_date': record.dates[-1].date().isoformat() if valid_prices else '',
        'currency': info.get('currency') or '',
        'fundamental': groups['fundamental'][0], 'fundamental_coverage': groups['fundamental'][1],
        'factor': groups['factor'][0], 'factor_coverage': groups['factor'][1],
        'technical': groups['technical'][0], 'technical_coverage': groups['technical'][1],
        'total': total, 'status': 'ranked' if complete else 'unranked', 'issues': '; '.join(issues),
    }


def rank(records: list[Record], now: datetime | None = None) -> list[dict[str, Any]]:
    symbols = [r.ticker for r in records]
    if not symbols or len(symbols) != len(set(symbols)):
        raise ValueError('Universe must be non-empty and contain unique symbols')
    rows = [score(r, now) for r in records]
    rows.sort(key=lambda r: (r['total'] is None, -(r['total'] or 0), r['ticker']))
    for i, row in enumerate(rows):
        row['rank'] = i + 1 if row['total'] is not None else None
    return rows
