# 0018 — Superbet fallback source + expanded sports coverage

Date: 2026-10-08. Status: decided. Extends 0017.

## Problem

One source (ESPN) meant one outage could blank or stale the board,
and the deterministic slate would be the only thing standing between
a dead ESPN and an empty storefront. Coverage was also thin: three
leagues, soccer + NFL only.

## Decision

1. Fallback chain in `Demo.sports_showcase`: EspnSportsEngine ->
   SuperbetSportsEngine -> deterministic slate (0016). The slate
   is now the last resort, never the first.
2. `SuperbetSportsEngine` (`frame/verticals/sports/superbet_engine.py`):
   real fixtures from Superbet's public v3 offer server
   (`production-superbet-offer-br.freetls.fastly.net/v3/pt-BR/events`,
   same endpoint cleanSheet's superbet_snapshot uses; no key),
   soccer only (`sport_id == 5`), 600s cache at
   `probes/superbet-cache.json`, prices from the same deterministic
   model — Superbet's own prices are NOT served. Gotchas encoded:
   `startDate` must be whole-hour precision (HTTP 400 otherwise),
   and `event_name` separates teams with `·` (U+00B7), rendered
   as mojibake when read as ASCII.
3. ESPN coverage expanded to 11 competitions: bra.1, ita.1, eng.1,
   esp.1, ger.1, fra.1, uefa.champions (soccer), nfl, nba, mlb, nhl.
   One scoreboard request per league per 120s cycle (~5.5 req/min
   — inside the conservative cleanSheet budget). Market recipes per
   sport: soccer 1x2 + total 2.5; nfl/nba/mlb/nhl moneyline +
   sport total (215.5 nba, 8.5 mlb, 5.5 nhl, 44.5 nfl), all
   priced by the same deterministic model.

## Verification

- Live: EspnSportsEngine 52 fixtures across 11 competitions (nba,
  mlb, nhl present); SuperbetSportsEngine 132 soccer fixtures;
  fallback chain + canned-feed contract tests green.
- Gates: `demo.test_demo` 80/80, `frame.selftest` 43/43,
  `verify.py` 0 problems.
