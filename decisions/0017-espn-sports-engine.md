# 0017 — SportsEngine on ESPN fixtures + in-house model prices

Date: 2026-10-08. Status: decided. Supersedes 0016's fixture slate
(the pricing model survives; the generated board does not).

## Problem

0016 priced a board the engine invented itself: real team names, but
games and kickoffs were a deterministic daily pairing, so nothing on
the site corresponded to the world. A betting site whose games don't
exist is a mockup wearing a sportsbook's clothes.

## Decision

`frame/verticals/sports/espn_engine.py` loads the `SportsEngine`
contract at `/api/sports`:

1. Fixtures and statuses come from the same source cleanSheet's
   edgewatch used: public ESPN scoreboards (`site.web.api`, no key),
   bra.1 / ita.1 / nfl. Responses cached at `probes/espn-cache.json`
   (120s TTL); stale cache keeps the site alive through an outage;
   no network + no cache => ProviderError.
2. Prices are NOT ESPN's. Every market is quoted by
   `frame/verticals/sports/pricing.py` — deterministic team strength
   -> Poisson 1x2/totals (soccer) or logistic moneyline + totals
   (NFL) -> uniform 5% margin -> decimal prices, repriced per 30s
   bucket with minute-scaled drift on live fixtures. Same input,
   same price, reproducible under test.
3. Server falls back to the 0016 deterministic slate only when ESPN
   and the cache are both dead, so a dead WAN never blanks the board.

## Consequences

- The sports view now shows tonight's real games (22 fixtures today)
  with house-model odds; the 15s polling still surfaces bucket drift.
- ESPN's DraftKings odds are deliberately not served: the site quotes
  its own book, consistent with the dog-food rule from 0016.
- Bet placement/settlement unchanged (client-locked price at
  placement, deterministic outcome unit, 45s delay).

## Verification

- Live smoke: 22 real fixtures (Santos x Flamengo etc.), `source:
  "espn"`, all markets priced by the model. `demo.test_demo` 79/79
  (+1 EspnSportsEngine contract test with a canned feed),
  `frame.selftest` 43/43, `verify.py` 0 problems.
