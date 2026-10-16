"""Shared in-house market board.

Every sports source quotes the *same* deterministic book for a given
(sport, home, away) fixture, so a source only ever has to supply fixtures —
never prices. Soccer carries the draw (1x2) plus an over/under 2.5; every
other sport carries a two-way moneyline plus a total on the sport's own
scale. Tennis is moneyline-only (a set/match has no draw to price).
"""

from __future__ import annotations

import time

from .contract import Market
from . import pricing as P

SOCCER_TOTAL_LINE = 2.5

# (base total, spread, line) for the sports priced off a point total
TOTALS = {
    "basketball": (222.0, 12.0, 215.5),
    "hockey": (6.2, 1.2, 5.5),
    "handball": (56.0, 8.0, 55.5),
    "baseball": (8.6, 1.6, 8.5),
    "volleyball": (3.8, 0.5, 4.5),
    "esports": (2.6, 0.5, 2.5),
    "futsal": (6.4, 1.2, 6.5),
    "cricket": (320.0, 30.0, 300.0),
}
DEFAULT_TOTAL = (2.7, 0.6, 2.5)


def _market(fixture_key: str, kind: str, selections, probs, bucket: int,
            minute: float, line: float | None = None) -> Market:
    prices = []
    for i, prob in enumerate(probs):
        ratio = 1.0 + P.drift(f"{fixture_key}:{kind}:{i}", bucket, minute)
        prices.append(max(1.01, round(P.to_price(prob) * ratio, 2)))
    return Market(key=f"{fixture_key}:{kind}", fixture_key=fixture_key,
                  kind=kind, selections=tuple(selections),
                  prices=tuple(prices), line=line)


def quote_markets(fixture_key: str, sport: str, home: str, away: str,
                  live: bool = False, minute: float = 0.0,
                  bucket: int | None = None) -> list[Market]:
    """The board for one fixture. Deterministic per 30s bucket; a live
    fixture adds the minute-scaled drift so the prices breathe."""
    if bucket is None:
        bucket = int(time.time()) // 30
    minute = minute if live else 0.0
    out: list[Market] = []

    if sport == "soccer":
        out.append(_market(fixture_key, "1x2", (home, "Draw", away),
                           P.soccer_probs(home, away), bucket, minute))
        over = P.total_probs_over(home, away, SOCCER_TOTAL_LINE)
        out.append(_market(fixture_key, "total", ("Over", "Under"),
                           (over, 1.0 - over), bucket, minute,
                           line=SOCCER_TOTAL_LINE))
        return out

    home_p = P.nfl_probs(home, away)
    out.append(_market(fixture_key, "moneyline", (home, away),
                       (home_p, 1.0 - home_p), bucket, minute))
    if sport == "tennis":
        return out
    if sport == "football":
        over = P.nfl_total(home, away)
        out.append(_market(fixture_key, "total", ("Over", "Under"),
                           (over, 1.0 - over), bucket, minute, line=43.5))
        return out

    base, scale, line = TOTALS.get(sport, DEFAULT_TOTAL)
    over = P.points_total_over(home, away, base, scale, line)
    out.append(_market(fixture_key, "total", ("Over", "Under"),
                       (over, 1.0 - over), bucket, minute, line=line))
    return out
