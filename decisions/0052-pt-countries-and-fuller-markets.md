# 0052 — Portuguese countries, a fuller market card and a ticking live minute

Date: 2026-10-16
Status: accepted

## Context

Three rounds of feedback on the 0051 board, all from the owner:

1. **Some country titles were English.** Flashscore sends the country in
   English (`Brazil`, `Czech Republic`) and the board grouped by that raw
   string — a Portuguese site should show `Brasil`, `Tchéquia`.
2. **The card was thin.** Tennis/basketball showed a two-way winner line
   only; the soccer total was hidden behind "mais mercados"; the owner asked
   for the draw to be offered, and for totals — goals in soccer, points in
   other sports, including per-half.
3. **Minute-by-minute status.** Wanted, with the owner's own caveat that a
   high-frequency poll could hammer the feed and get the IP blocked.

## Decision

### 1. Countries are translated once, in an engine-shared map

`frame/verticals/sports/locale_pt.py` holds ~150 country names
(observed-in-feed + neighbours the feeds rotate in) and `pt(name)` — the
Portuguese name, or the source spelling when unknown. Both Flashscore (`ZY`)
and Livescore (`Cnm`) run the country through it **at parse time**, because
the country is the first grouping key in the UI: translating at render time
would let one country appear twice (`Brazil` and `Brasil`). A probe of all
ten sports feeds found 146 distinct names; after the map, `/api/sports`
carries zero untranslated leftovers (and 36 international fixtures group
under "Internacional").

### 2. The market board is a real card, not a single line

`marketboard.quote_markets` now returns the **result + the total side by
side in the row**, with the rest an expandable away:

- **soccer** — 1x2 (with Empate), total 2.5, dupla chance (1X/12/X2), ambas
  marcam (Sim/Não), and 1st/2nd-half totals on the same grid;
- **clock sports that can tie** (futsal, handball, hockey, rugby, football) —
  three-way 1x2 + total + half totals;
- **two-way sports** (tennis, basketball, baseball, volleyball, esports…) —
  moneyline + total on the sport's own scale (+ half totals for basketball);
  **no Empate button where a draw cannot happen** — a market that can never
  settle is a fake, and no real card offers one;
- tennis gains a total-games market (line 21.5).

The draw probability is `match_probs` (independent Poissons on a shared
total), floored per sport — `DRAW_FLOOR` (handball 9%, hockey 20%, futsal
12%, rugby 5%, football 2.5%) — so a regulation tie prices like a real book
instead of a Poisson artifact (a λ≈56 tie once printed 150.00).

Pricing gains: `match_probs`, `both_score` and a `factor` on the total
over-probabilities (a half's expected total = full game × 0.45/0.55).

### 3. The live minute ticks between polls, with zero extra requests

A minute-by-minute push would mean polling Flashscore every few seconds —
exactly the pressure that gets an IP blocked. Instead the minute is already
derived from the kickoff, so the **client advances it locally**: the board
renders from `Date.now()` (ticking every 10s), the source's own minute label
(e.g. Livescore's `24'`) takes precedence, and set/innings sports (tennis,
volleyball, baseball, esports) show just the pulsing live dot — `_sports_progress`
now minute-caps only the clock sports, so a tennis match can no longer print
a fake `90+'`. Scores still refresh server-side on the 15s poll; only the
clock is local.

## Alternatives considered

1. **A draw button on every sport.** Rejected (recorded above): our book has
   to be *settleable*; the owner's "it should have a draw odd" is satisfied
   everywhere the rules allow one.
2. **Minute-by-minute feed polling (30–60s TTL).** Deferred, per the
   owner's own caution about server pressure and blocking; the local clock
   gives the minute to minute feel for free.
3. **Machine-translate every country.** Rejected: a 150-entry static map is
   deterministic, offline and reviewable; a live translator is a network
   dependency for a string.

## Notes

- Suites: `frame` 45/45, `demo` 282/282 (+1 market-board shape test; the
  Flashscore contract test now asserts pt countries + the Empate/btts
  markets), `verify.py` 0; export rebuilt.
- Live probe (post-fix): 320 fixtures / 9 sports, soccer card = 1x2 + total
  + dc + btts + 2 half totals, hockey draw 4.75, handball draw 10.5,
  tennis shows a live dot without a minute, `errors: []`.
- True push updates (short-TTL live-only refresh or SSE) remain the
  follow-up if the owner wants score-by-score movements.
