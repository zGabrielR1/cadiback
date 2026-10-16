"""Shared in-house market board.

Every sports source quotes the *same* deterministic book for a given
(sport, home, away) fixture, so a source only ever has to supply fixtures —
never prices. The result market carries a draw only for the sports whose
rules can actually end in one; offering a draw on tennis would be a market
that can never settle. Two-way sports get a winner line, soccer adds both-
teams-to-score, and every sport with a total gets its full-game line plus
first/second-half fragments, so a row offers what a real card offers.
"""

from __future__ import annotations

import time

from .contract import Market
from . import pricing as P

SOCCER_TOTAL_LINE = 2.5

# sports whose rules can end tied: three-way result (1 X 2)
DRAW_SPORTS = {"soccer", "futsal", "handball", "hockey", "rugby", "football"}
# regulation ties happen more than independent Poissons give credit for in a
# high-scoring clock sport — floor the draw, then rescale the two wins back to
# a unit total (a real card: handball ~10%, hockey ~20%)
DRAW_FLOOR = {"handball": 0.09, "hockey": 0.20, "futsal": 0.12,
              "rugby": 0.05, "football": 0.025}
# expected total per sport, for the draw probability and the totals
TOTALS = {
    "basketball": (222.0, 12.0, 215.5),
    "hockey": (6.2, 1.2, 5.5),
    "handball": (56.0, 8.0, 55.5),
    "baseball": (8.6, 1.6, 8.5),
    "volleyball": (3.8, 0.5, 4.5),
    "tennis": (22.0, 1.5, 21.5),
    "esports": (2.6, 0.5, 2.5),
    "futsal": (6.4, 1.2, 6.5),
    "cricket": (320.0, 30.0, 300.0),
}
DEFAULT_TOTAL = (2.7, 0.6, 2.5)
RUGBY_TOTAL = (44.0, 4.0, 43.5)


def _market(fixture_key: str, kind: str, selections, probs, bucket: int,
            minute: float, line: float | None = None) -> Market:
    prices = []
    for i, prob in enumerate(probs):
        ratio = 1.0 + P.drift(f"{fixture_key}:{kind}:{i}", bucket, minute)
        prices.append(max(1.01, round(P.to_price(prob) * ratio, 2)))
    return Market(key=f"{fixture_key}:{kind}", fixture_key=fixture_key,
                  kind=kind, selections=tuple(selections),
                  prices=tuple(prices), line=line)


def _half_line(line: float) -> tuple[float, float]:
    """The p/2-ish totals for the two halves, on the book's own .5 grid."""
    return round(line * 0.45 * 2) / 2.0, round(line * 0.55 * 2) / 2.0


def quote_markets(fixture_key: str, sport: str, home: str, away: str,
                  live: bool = False, minute: float = 0.0,
                  bucket: int | None = None) -> list[Market]:
    """The book for one fixture. Deterministic per 30s bucket; a live
    fixture adds the minute-scaled drift so the prices breathe."""
    if bucket is None:
        bucket = int(time.time()) // 30
    minute = minute if live else 0.0

    def add(kind, selections, probs, line=None):
        return _market(fixture_key, kind, selections, probs, bucket, minute,
                       line=line)

    result: Market
    totals: list[Market] = []
    extras: list[Market] = []

    if sport == "soccer":
        probs = P.soccer_probs(home, away)
        result = add("1x2", (home, "Empate", away), probs)
        extras.append(add("dc", ("1X", "12", "X2"),
                          (probs[0] + probs[1], probs[0] + probs[2],
                           probs[1] + probs[2])))
        extras.append(add("btts", ("Sim", "N\u00e3o"),
                          (P.both_score(home, away),
                           1.0 - P.both_score(home, away))))
        over = P.total_probs_over(home, away, SOCCER_TOTAL_LINE)
        line1, line2 = _half_line(SOCCER_TOTAL_LINE)
        extras.append(add("total-h1", ("Mais", "Menos"),
                          (P.total_probs_over(home, away, line1, 0.45),
                           1.0 - P.total_probs_over(home, away, line1, 0.45)),
                          line=line1))
        extras.append(add("total-h2", ("Mais", "Menos"),
                          (P.total_probs_over(home, away, line2, 0.55),
                           1.0 - P.total_probs_over(home, away, line2, 0.55)),
                          line=line2))
        totals.append(add("total", ("Mais", "Menos"), (over, 1.0 - over),
                          line=SOCCER_TOTAL_LINE))
        return [result, totals[0], *extras]

    if sport in DRAW_SPORTS:
        base, scale, line = (RUGBY_TOTAL if sport == "rugby" else
                             (43.5, 8.0, 45.5) if sport == "football" else
                             TOTALS.get(sport, DEFAULT_TOTAL))
        probs = P.match_probs(home, away, base)
        floor = DRAW_FLOOR.get(sport, 0.0)
        if probs[1] < floor:
            spread = probs[0] + probs[2]
            if spread > 0:
                probs = ((1.0 - floor) * probs[0] / spread, floor,
                         (1.0 - floor) * probs[2] / spread)
        result = add("1x2", (home, "Empate", away), probs)
        line1, line2 = _half_line(line)
        extras.append(add("total-h1", ("Mais", "Menos"),
                          (P.points_total_over(home, away, base, scale,
                                               line1, 0.45),
                           1.0 - P.points_total_over(home, away, base, scale,
                                                     line1, 0.45)),
                          line=line1))
        extras.append(add("total-h2", ("Mais", "Menos"),
                          (P.points_total_over(home, away, base, scale,
                                               line2, 0.55),
                           1.0 - P.points_total_over(home, away, base, scale,
                                                     line2, 0.55)),
                          line=line2))
        over = P.points_total_over(home, away, base, scale, line)
        totals.append(add("total", ("Mais", "Menos"), (over, 1.0 - over),
                          line=line))
        return [result, totals[0], *extras]

    home_p = P.nfl_probs(home, away)
    result = add("moneyline", (home, away), (home_p, 1.0 - home_p))
    if sport == "tennis":
        base, scale, line = TOTALS["tennis"]
        over = P.points_total_over(home, away, base, scale, line)
        totals.append(add("total", ("Mais", "Menos"), (over, 1.0 - over),
                          line=line))
        return [result, totals[0], *extras]

    base, scale, line = TOTALS.get(sport, DEFAULT_TOTAL)
    if sport == "basketball":
        line1, line2 = _half_line(line)
        extras.append(add("total-h1", ("Mais", "Menos"),
                          (P.points_total_over(home, away, base, scale,
                                               line1, 0.47),
                           1.0 - P.points_total_over(home, away, base, scale,
                                                     line1, 0.47)),
                          line=line1))
        extras.append(add("total-h2", ("Mais", "Menos"),
                          (P.points_total_over(home, away, base, scale,
                                               line2, 0.53),
                           1.0 - P.points_total_over(home, away, base, scale,
                                                     line2, 0.53)),
                          line=line2))
    over = P.points_total_over(home, away, base, scale, line)
    totals.append(add("total", ("Mais", "Menos"), (over, 1.0 - over),
                      line=line))
    return [result, totals[0], *extras]
