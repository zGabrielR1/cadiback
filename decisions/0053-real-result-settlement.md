# 0053 — Sports slips settle against the real result

Date: 2026-10-16
Status: accepted

## Context

The critical review of 0051 + 0052 named one problem above all others:

> **Settlement is fake.** `bet()` stored `unit = sha256(fixture|selection|bet_id)`
> and `settle_pending()` settled it **45 seconds later by hash roll**. Every
> odds board, market and betslip culminated in a slot-machine draw — a bet
> never settled by what actually happened on the pitch.

That contradicts the point of a 1:1 replica, and everything needed to fix it
was already on the table: the feed carries final status + both scores
per fixture, `rounds.jsonl` persists `pendente` rows, and `settle_pending()`
already runs on every `/api/sports`, `/api/bet` and POST `/api/settle`.
Only the verdict function was wrong.

## Decision

### 1. One module maps a market onto the final score

`frame/verticals/sports/settlement.py` — `resolve(kind, selection, home,
away, home_score, away_score, line)` is a pure function returning:

- `"won"` — the stake pays stake × the bought price;
- `"lost"` — the stake goes to the house;
- `"push"` — refund at odds 1.00 (the defensive tie case of a two-way
  market; full-game lines live on the .5 grid so this is rare by design);
- `None` — **the result does not determine the market** (match not final, a
  half market the full score cannot decide). `None` means *stay pending*,
  never an invented verdict.

It answers 1x2 (by team name or Casa/Empate/Fora), moneyline (with push),
dupla chance, ambas marcam, and totals — full game (over/under/push on the
integer grid) and half fragments. A half's total is an integer and the other
half owns the remainder, so `Mais 25.0` on the first half is decisively
**lost** once the FULL total is ≤ 25 (each half tops out at the full total),
while the covering direction can stay undetermined.

### 2. The slip carries its legs; the verdict is per-leg, all-or-nothing

`bet()` now persists the legs on the round row (`fixture_key`, `selection`,
`price`, `market_kind`, `home`, `away`, `line`) — the shape settlement
needs. `Demo._settle_verdict` walks the legs against the result index: any
losing leg settles the whole express as a loss; a push anywhere (and no
loss) refunds the slip; any undetermined leg leaves the whole slip pending.
Each settled row records `settled_by: "result"` and a human-readable `note`
(`Flamengo 2:1 Santos → won`) so the player can audit what happened.

### 3. Result first, simulation only as a declared, stale fallback

`settle_pending` orders the sources honestly:

1. **the live board** — `/api/sports` donates the payload it just fetched
   (`settle_pending(payload=payload)`), so settling costs zero extra calls;
2. **the lazy archive** — `FlashscoreSportsEngine.results()` pulls
   yesterday's *and* today's finals (the board keeps only its 320
   most-relevant rows; a morning final can drop off it), with its own
   15-minute cache (`probes/flashscore-results-cache.json`), fetched only
   when a leg is missing from the board, and **only then**;
3. **nothing → the slip stays pending** while the match can still decide it
   (under `STALE_BET_SECONDS = 12 h`);
4. **after 12 h of silence**, the legacy deterministic draw settles it with
   an honest note (`resultado não confirmado há N h — simulado`) — a
   declared simulation, not a silent one.

Slips without legs (the dog-food synthetic path) keep the classic 45 s
settlement, so nothing outside the board changes.

### 4. A push is the books' own posting

`settle_bet_win(..., "1.00")` is rejected by the money layer (odds below
1.01) — a push goes through `Books.settle_bet_push`, which returns the cash
portion to the balance and the bonus portion to bonus, exactly like a real
card's estorno. The first test run caught this; it is now enforced by
`test_losing_leg_takes_the_stake_and_a_push_refunds`.

### 5. The account view tells the truth about a refund

`AccountView` renders the new `anulada` tier as `ANULADA · estorno @ 1.00`
(previously it fell through to the DERROTA badge) and prints the settlement
`note` under the badge — the real score the verdict came from.

## Alternatives considered

1. **Settle from the score the client reports.** Rejected: the client is not
   a source of truth on a money path; the feed the server already trusts is.
2. **Settle the instant status flips to final, per fixture, on a live
   poll.** Deferred: it means a per-fixture watcher hammering the feed —
   the exact pressure that gets an IP blocked (the owner's own caveat in
   0052). The board's 15 s poll plus the archive is enough to settle every
   slip within a poll of its final whistle.
3. **Keep the hash roll as the verdict and only *display* the real score.**
   Rejected outright — that is the problem this decision exists to remove.

## Notes

- Suites: `frame` 45/45, `demo` 289/289 (+7 in `SportsSettlementTest`:
  the resolve matrix, a result-settled win, loss + push through the books,
  an express killed by one dead leg, an undetermined slip held then settled
  from the archive, a stale slip declaring its simulation, and the
  Flashscore finals archive), `verify.py` 0; export rebuilt.
- Milestones from the review: **M1 done here**; M2 = "Minhas apostas"
  (open/settled slip list), M3 = score-aware in-play repricing, M4 =
  match-detail page (full market ladder), M5 = feed resilience (mirror,
  SWR).
- Live verification (2026-10-16, shipped commit `f58d072`): Render deploy
  `dep-db98e3hsrm7s73bcrlu0` live — `/api/health` 200 (receipt fresh,
  books balance), `/api/catalog` 200, `/` 200, and `/api/sports` 200
  from the production container: Flashscore, 320 fixtures, 98 in play,
  `errors: []`, every market kind present (1x2, dc, btts, moneyline,
  total, total-h1, total-h2) with lines — so the deployed settlement has
  everything it needs to decide a slip. Vercel `cadiback-web` redeployed;
  storefront 200, `/api/health` through its same-origin rewrite returns
  the backend's payload (Turnstile hostnames still carry both hosts), and
  the served chunk contains the `ANULADA` badge and the real-result
  confirmation message. No Supabase migration: rounds are JSONL, the new
  `legs`/`settled_by`/`note` fields are free-form JSON.
