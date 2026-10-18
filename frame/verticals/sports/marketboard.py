"""Shared in-house market board.

Every sports source quotes the *same* deterministic book for a given
(sport, home, away) fixture, so a source only ever has to supply fixtures —
never prices. The result market carries a draw only for the sports whose
rules can actually end in one; offering a draw on tennis would be a market
that can never settle. Two-way sports get a winner line, soccer adds both-
teams-to-score and dupla chance, and every sport with a total gets its
full-game line plus first/second-half fragments, so a row offers what a real
card offers.

Two more markets a real card always has: **draw-no-bet** (`dnb`, a draw
refunds) and an **asian handicap** (`ah`, the home side giving a goal on the
clock sports). Both settle off the final score (`settlement.resolve`) and both
are priced by `pricing` with the same exact-overround rule as the rest of the
book. When a fixture is live the result market is tilted by the running score
through `pricing.inplay_probs`, so a 2-0 lead shortens the leader instead of
leaving the pre-match price untouched.
"""

from __future__ import annotations

import math
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
# Counting markets read straight off the match-stats feed (stats_engine): the
# stats key whose two sides sum to the count, the market kind, and the expected
# full-match total. The line quoted is derived from the model (expected final
# count, snapped to the book's .5 grid) so it moves with the clock like a real
# in-play count line, rather than sitting on a fixed number all match.
COUNT_MARKETS = (
    ("yellow_cards", "cards", 4.4),
    ("corners", "corners", 10.2),
    ("fouls", "fouls", 23.0),
)
# the live clock cap per sport, for the in-play tilt (mirrors the engines')
LIVE_CAP = {"soccer": 90.0, "futsal": 40.0, "handball": 60.0,
            "basketball": 48.0, "hockey": 60.0, "rugby": 80.0,
            "football": 60.0}


def _market(fixture_key: str, sport: str, kind: str, selections, probs,
            bucket: int, minute: float, line: float | None = None) -> Market:
    prices = P.price_market(fixture_key, kind, probs,
                            margin=P.margin_for(sport, kind),
                            bias=P.bias_for(kind), bucket=bucket, minute=minute)
    return Market(key=f"{fixture_key}:{kind}", fixture_key=fixture_key,
                  kind=kind, selections=tuple(selections),
                  prices=tuple(prices), line=line)


def _half_line(line: float) -> tuple[float, float]:
    """The p/2-ish totals for the two halves, on the book's own .5 grid."""
    return round(line * 0.45 * 2) / 2.0, round(line * 0.55 * 2) / 2.0


def quote_markets(fixture_key: str, sport: str, home: str, away: str,
                  live: bool = False, minute: float = 0.0,
                  bucket: int | None = None, home_score: int | None = None,
                  away_score: int | None = None, stats: dict | None = None) -> list[Market]:
    """The book for one fixture. Deterministic per 30s bucket; a live fixture
    adds the minute-scaled drift and tilts the result market by the score.

    `stats` is the parsed match-stats section (`stats_engine.match_stats`).
    When it carries a counting stat (cards, corners, fouls) the board adds that
    over/under line, priced from the count so far and the time left; without it
    the market is simply not offered — a count with no feed behind it cannot be
    settled, so it must not be quoted.
    """
    if bucket is None:
        bucket = int(time.time()) // 30
    minute = minute if live else 0.0
    hs, as_ = (home_score, away_score) if live else (None, None)

    def add(kind, selections, probs, line=None, tilt=False):
        if tilt and live:
            probs = P.inplay_probs(kind, probs, hs, as_, minute,
                                   cap=LIVE_CAP.get(str(sport or ""), 90.0))
        return _market(fixture_key, sport, kind, selections, probs, bucket,
                       minute, line=line)

    def count_lines(section, frac):
        """The over/under lines for whatever counting stats the feed carries.

        Only offered in-play: a pre-match count with no stats behind it could
        not be settled from the final score, so it is not quoted (the board's
        pre-match book is the result/total market).
        """
        if not live:
            return []
        out = []
        for key, kind, mean in COUNT_MARKETS:
            pair = (section or {}).get(key)
            if not pair:
                continue
            current = sum(float(v or 0) for v in pair)
            remaining = max(0.0, mean * (1.0 - max(0.0, min(1.0, frac))))
            line = max(0.5, math.floor(current + remaining) + 0.5)
            over = P.count_over(current, mean, frac, line)
            out.append(add(kind, ("Mais", "Menos"), (over, 1.0 - over),
                           line=line))
        return out

    def match_section():
        return (stats or {}).get("match") or stats or {}

    def result_extras(three):
        """dnb + ah derived from a (home, draw, away) result vector."""
        home_p, _draw, away_p = three
        out = []
        if home_p + away_p > 0:
            out.append(add("dnb", (home, away), (home_p, away_p)))
            hcap = -1.0 if home_p >= away_p else 1.0
            out.append(add("ah", (home, away),
                           P.handicap_two_way(home_p, away_p, hcap),
                           line=hcap))
        return out

    def halves(kind_a, kind_b, over_a, over_b, line1, line2):
        return [
            add(kind_a, ("Mais", "Menos"), (over_a, 1.0 - over_a), line=line1),
            add(kind_b, ("Mais", "Menos"), (over_b, 1.0 - over_b), line=line2),
        ]

    totals: list[Market] = []
    extras: list[Market] = []

    if sport == "soccer":
        raw = list(P.normalize(P.soccer_probs(home, away)))
        adj = (P.inplay_probs("1x2", raw, hs, as_, minute,
                              cap=LIVE_CAP["soccer"]) if live else raw)
        result = _market(fixture_key, sport, "1x2", (home, "Empate", away),
                         adj, bucket, minute)
        extras.append(add("dc", ("1X", "12", "X2"),
                          (adj[0] + adj[1], adj[0] + adj[2], adj[1] + adj[2])))
        both = P.both_score(home, away)
        extras.append(add("btts", ("Sim", "N\u00e3o"), (both, 1.0 - both)))
        over = P.total_probs_over(home, away, SOCCER_TOTAL_LINE)
        line1, line2 = _half_line(SOCCER_TOTAL_LINE)
        extras.extend(halves(
            "total-h1", "total-h2",
            P.total_probs_over(home, away, line1, 0.45),
            P.total_probs_over(home, away, line2, 0.55), line1, line2))
        extras.extend(result_extras(adj))
        extras.extend(count_lines(
            match_section(), minute / LIVE_CAP["soccer"] if live else 0.0))
        totals.append(add("total", ("Mais", "Menos"), (over, 1.0 - over),
                          line=SOCCER_TOTAL_LINE))
        return [result, totals[0], *extras]

    if sport in DRAW_SPORTS:
        base, scale, line = (RUGBY_TOTAL if sport == "rugby" else
                             (43.5, 8.0, 45.5) if sport == "football" else
                             TOTALS.get(sport, DEFAULT_TOTAL))
        raw = list(P.match_probs(home, away, base))
        floor = DRAW_FLOOR.get(sport, 0.0)
        if raw[1] < floor:
            spread = raw[0] + raw[2]
            if spread > 0:
                raw = [(1.0 - floor) * raw[0] / spread, floor,
                       (1.0 - floor) * raw[2] / spread]
        adj = (P.inplay_probs("1x2", raw, hs, as_, minute,
                              cap=LIVE_CAP.get(sport, 90.0)) if live else raw)
        result = _market(fixture_key, sport, "1x2", (home, "Empate", away),
                         adj, bucket, minute)
        line1, line2 = _half_line(line)
        extras.extend(halves(
            "total-h1", "total-h2",
            P.points_total_over(home, away, base, scale, line1, 0.45),
            P.points_total_over(home, away, base, scale, line2, 0.55),
            line1, line2))
        extras.extend(result_extras(adj))
        extras.extend(count_lines(
            match_section(),
            minute / LIVE_CAP.get(sport, 90.0) if live else 0.0))
        over = P.points_total_over(home, away, base, scale, line)
        totals.append(add("total", ("Mais", "Menos"), (over, 1.0 - over),
                          line=line))
        return [result, totals[0], *extras]

    home_p = P.nfl_probs(home, away)
    result = add("moneyline", (home, away), (home_p, 1.0 - home_p), tilt=True)
    base, scale, line = TOTALS.get(sport, DEFAULT_TOTAL)
    if sport == "tennis":
        over = P.points_total_over(home, away, base, scale, line)
        totals.append(add("total", ("Mais", "Menos"), (over, 1.0 - over),
                          line=line))
        return [result, totals[0], *extras]
    line1, line2 = _half_line(line)
    extras.extend(halves(
        "total-h1", "total-h2",
        P.points_total_over(home, away, base, scale, line1,
                            0.47 if sport == "basketball" else 0.45),
        P.points_total_over(home, away, base, scale, line2,
                            0.53 if sport == "basketball" else 0.55),
        line1, line2))
    over = P.points_total_over(home, away, base, scale, line)
    totals.append(add("total", ("Mais", "Menos"), (over, 1.0 - over),
                      line=line))
    return [result, totals[0], *extras]
