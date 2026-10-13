# 0016 — In-house odds engine replaces the capture seam

Date: 2026-10-08. Status: decided.

## Problem

`/api/sports` served a stale 2026-10-01 capture from
`probes/live-fixtures.json` (mostly unpriced markets, frozen kickoffs)
behind a 30s SHA256 wobble. The section looked alive but had no real
delivery: prices had no model, markets were static, and the source sat
one import away from being mistaken for official data.

## Decision

Dog food: `demo/odds_engine.py` is the odds delivery.

1. Fixture board from a deterministic daily pairing of real team pools
   (bra.1, ita.1, nfl; `TEAMS` in the engine): three competitions, three
   kickoff windows, fixtures carry status SCHEDULED / IN_PROGRESS /
   STATUS_FINAL and finished games leave the board.
2. Prices from a real model: per-team deterministic strength → Poisson
   win/draw/loss and totals probabilities → uniform 5% book margin →
   decimal prices. NFL uses a logistic moneyline and a Poisson totals
   line at 44.5.
3. Deterministic per 30s bucket: same bucket, same payload; a live
   fixture's drift scales with match minute, so prices breathe on the
   polling cadence instead of jumping.
4. Provenance is explicit: `source: "inhouse"`, `licensed_feed: false`,
   provider "in-house odds engine (deterministic)". The ESPN capture
   loader (`sports_data.load_live`) survives only as a fact source for
   the news panel.

## Consequences

- Sports section, casino pricing strip, admin `pending_sports`, and bet
  placement all consume the engine feed unchanged (same envelope).
- Sports bet settlement flow (price recorded at placement, deterministic
  `unit` outcome, 45s delay) is untouched.
- SharpAPI.io was deliberately not used: the dog-food engine is
  dependency-free, offline, and reproducible under test.

## Verification

- `demo.test_demo` 78/78 (+1 engine-determinism check), `frame.selftest`
  43/43, `verify.py` 0 problems; live smoke on `/api/sports` serves
  36 in-house fixtures with 1x2/total (soccer) and moneyline/total
  (nfl) markets.
