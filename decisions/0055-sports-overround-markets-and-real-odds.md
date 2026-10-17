# 0055 — A per-market overround, a fuller card, and a real-odds overlay

Date: 2026-10-17
Status: accepted

## Context

The sports book was priced by a flat 5% multiplicative margin
(`to_price(prob) = 1/(prob·1.05)`), and the live drift multiplied each *price*
independently — so a market's overround wobbled off 5% whenever the drift fired,
and the rounding was per leg. The card was thin (1x2/total/halves), the outcome
markets ignored the running score entirely, and no provider price was ever
served even when a source published one.

The ask was "a better odds system" — all three of: a realistic margin model,
more markets with live movement, and real bookmaker odds where available — plus
larger sport icons on desktop.

## Decision

### 1. `pricing.price_market` — the overround is the target, by construction

A market is priced by ``o_i = (1+margin)·p_i^k / Σ p_j^k`` with ``price_i =
1/o_i``; the overround is exactly `margin` before rounding, and a cent-grid
correction (`_cent_fix`) nudges the shortest-priced leg so the *delivered* book
lands as close to it as two decimals allow. `k` (`KIND_BIAS`) shapes the
favourite–longshot distribution: 1.0 is a flat margin, >1 puts relatively more
margin on the long side, like a real book. An extreme favourite clamps at 1.01
and carries *less* margin — a floor, never a fatter book.

- `SPORT_MARGIN` sets the base per sport; `KIND_MARGIN` adds for derivatives
  (dc, btts, halves, ah, dnb).
- The per-30s drift is applied to the **probabilities** and renormalized
  (`drift_probs`), so it moves the shape of the book without changing how much
  margin it holds — which multiplying each price by `1+d` did not.
- `to_price` and `drift` are kept as back-compat wrappers: the in-house slate
  (`demo/odds_engine.py`) and the frame tests still call them.

### 2. More markets, settled off the final score

`marketboard.quote_markets` adds **draw-no-bet** (`dnb`, a draw refunds) and an
**asian handicap** (`ah`, the home side giving a goal on the clock sports), and
gives the remaining two-way sports (`volleyball`, `baseball`, `esports`,
`cricket`) their half-total fragments. Handicap probabilities come from
`pricing.handicap_two_way` — a bounded log-odds shift of the two-way result, not
a full goal-difference model. Every new market **settles** (`settlement.resolve`
gains `dnb` and `ah`): a level final is a push, an exact handicap is a push.

### 3. The result market moves with the score

`pricing.inplay_probs` tilts a live result book toward the current leader, and
toward the draw when the match is level and late. The engines pass
`home_score`/`away_score` into `quote_markets`, so a 2-0 lead shortens the
leader instead of leaving the pre-match price untouched. It is deterministic and
bounded — the pre-match model is the base, the score only tilts it.

### 4. A real published price is served, and labelled

`Market` gains `source` (`"model"` or `"market"`). Where **ESPN publishes a
moneyline** — the one source we already read that carries prices — that price is
served verbatim (`source="market"`) and the rest of the card stays our model.
`Demo.sports_showcase` serializes `pricing` and `margin` per market, and the
board shows a small "mercado" chip, so a modelled price is never passed off as a
provider's. This is honest about its limits: Flashscore/Livescore publish no
odds, and ESPN is 403 from Render's egress — so in production the overlay often
will not appear, and the model carries the board.

### 5. The icons carry the board on a desktop

`web/app/globals.css` gains a `@media (min-width: 761px)` block (and a
`1400px` step) enlarging `.sx-tab-icon` (15px → 22px → 26px) alongside the tab
padding and odds column. The phone's `<=640px` block is untouched.

## Alternatives considered

1. **Keep the flat 5% margin.** Rejected: the drift made the overround drift,
   and one margin for a 3-way result, a both-teams-to-score and a half-total is
   not what a card does.
2. **Pull real odds from another source.** Deferred: every alternative needs an
   API key (a vendor account we do not have); ESPN's published moneyline is the
   one credential-free price already in the feed we read.
3. **Trim the totals for elapsed time when live.** Deferred: the result market
   is the headline and the one a score most clearly moves; a live total is a
   rest-of-game book of its own, not a nudge.
4. **Offer alternate total lines (1.5 / 2.5 / 3.5).** Deferred: the engines
   derive a fixture key from the market key by stripping the last segment, so a
   line in the key would need that lookup reworked; dnb/ah cover the "more
   markets" ask without it.

## Notes

- Suites: frame 50/50 (+5 `SportsPricingTest`), demo 300/300 (+3 odds tests,
  `test_marketboard_shapes_per_sport` extended for dnb/ah), `verify.py` 0;
  export rebuilt. Decision 0055.
- Files: `frame/verticals/sports/pricing.py`, `marketboard.py`,
  `settlement.py`, `contract.py`, `espn_engine.py`, `flashscore_engine.py`,
  `livescore_engine.py`; `demo/server.py` (`sports_showcase` provenance);
  `demo/test_demo.py`, `frame/tests/test_frame.py`;
  `web/app/components/SportsHome.jsx`, `web/app/globals.css`.
- `Market.source` defaults to `"model"`, so any caller that constructs a
  `Market` positionally is unaffected.
