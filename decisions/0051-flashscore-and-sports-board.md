# 0051 — Flashscore as the primary feed + a sport-separated sports board

Date: 2026-10-16
Status: accepted

## Context

Two problems with the sports surface, both raised by the owner right after
0050 shipped the first live feed:

1. **The `Ao vivo` view was unreadable.** Every fixture's competition was
   rendered as one flat row of chips — "all the games and their leagues" on
   one line — with no separation by sport, no grouping, and no score: the
   board showed team names and prices but never the *running score*, which is
   the one fact a live board exists to show.
2. **The feed carried one sport.** Livescore's public endpoint (0050) is
   soccer-only, and ESPN's scoreboard is 403 from datacenter egress. A board
   that only ever shows football is not a sportsbook.

The owner asked for Flashscore as the source (ideally primary) and for a
Sofascore-shaped UI: score placement, bet odds, and the option density a real
betting site has.

## Decision

### 1. Flashscore is the primary source; every source shares one market board

- `frame/verticals/sports/flashscore_engine.py` reads Flashscore's public
  match feed (`global.flashscore.ninja/2/x/feed/f_<sport>_<day>_3_en_1`,
  no key, only an `x-fsign` header). One feed format covers **every sport it
  carries**, and the payload ships the facts a board prints: country, league,
  kickoff, status code (`1` scheduled / `2` in play / `3` finished) and the
  live score (`AG`/`AH`). Verified 200 from **both** this machine and a cloud
  egress (the browser-honest hosts also answer, but the `.ninja` host is the
  stable one). Sports pulled: soccer, tennis, basketball, hockey, baseball,
  handball, rugby, volleyball, e-sports, futsal; the busiest three also pull
  tomorrow. Requests run on a small thread pool so one refresh stays ~2–3s.
- Flashscore's own prices are **not** served — several of its sports have no
  draw (tennis) or a different money shape, and delivery must never depend on
  a bookmaker's payload. Every quote comes from the new shared
  `frame/verticals/sports/marketboard.py`: soccer gets 1x2 + a 2.5 total,
  every other sport a two-way moneyline + a total on its own scale, tennis
  moneyline-only. Livescore and ESPN now delegate to the same board, so a
  source only ever has to supply fixtures.
- `Fixture` gained `country`, `home_score`, `away_score` and `progress`;
  `Market` gained the `line`. `Demo.sports_showcase` order is **Flashscore →
  Livescore → ESPN → deterministic slate**, with each failure recorded as
  before.

### 2. The board is separated by sport, then country → league, Sofascore-shaped

`SportsHome.jsx` was rewritten:

- **Sport tabs** (icon + label + fixture count + live count), ordered
  Futebol → Basquete → Tênis → … Only sports with games today appear.
- **Country → league grouping**, both collapsible, a per-league live count,
  and a "só ao vivo" filter usable inside a sport (not only from the nav).
- **Fixture rows** carry state on the left (kickoff time, or a pulsing live
  minute, or `ENC`), the two teams **stacked** with the score **right-aligned**
  and the leader emphasised, and a **fixed odds column** of compact
  tick/price buttons (1 · X · 2, or 1 · 2, or Mais/Menos). Extra markets
  (the total) expand under "mais mercados". The betslip contract is unchanged.

### 3. The Poisson model no longer overflows on a large total

`pricing._poisson` computed `lmbda**k / k!` directly, which overflowed for
basketball (~220 points) and cricket (~300) — a real crash that the
soccer-only board had hidden. It is now the recurrence `p_k = p_{k-1}·λ/k`
with a shared `_poisson_cdf`, so any total is priced robustly.

## Alternatives considered

1. **Keep Livescore primary and add Flashscore after it.** Rejected: the ask
   was Flashscore first, and it is strictly broader (every sport, plus scores
   for all of them) for the same keyless cost.
2. **Serve Flashscore's own odds.** Rejected: not all its sports carry a
   three-way book, the values are a third party's, and our whole delivery
   model is dog-food (own prices, own margin).
3. **Scrape the Flashscore HTML.** Rejected: the feed endpoint is the same
   data the page renders, in a stable line format, with no browser needed.
4. **A per-match detail page.** Deferred: the list row + expandable extra
   markets already carries the score, the main market and the totals; a full
   match page is a larger feature than this feedback pass.

## Notes

- `.dockerignore` keeps `probes/*cache*.json` out of the image, so the
  Flashscore snapshot is runtime-generated like the others; the source is
  reachable, not cached.
- Suites: `frame` 45/45, `demo` 281/281 (+1 Flashscore contract test),
  `verify.py` 0; export rebuilt.
- Multi-sport means the pricing board is exercised on totals it never saw
  before (that is what surfaced the overflow).
- **Live-verified** (both origins): `/api/sports` returns
  `source: "flashscore"`, 320 priced fixtures across 9 sports — 54 in play,
  every one carrying a score, 56 countries — with `errors: []`, directly on
  Render **and** through the Vercel `/api` proxy; the rewritten board is in the
  shipped Vercel chunk (`sx-league`, `mais mercados`, `só ao vivo`).
