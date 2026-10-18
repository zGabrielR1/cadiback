# 0061 — The anytime-scorer market, priced off the lineup slots

Date: 2026-10-18
Status: accepted (shipped)

## Context

Item 4 of decision 0057 asked for a richer sports channel, "player X scores"
among the markets. The count markets (`cards`, `corners`, `fouls`) already
shipped; the scorer market was held back because it needs two feeds the board
did not read — the **lineups** (who is on the pitch) for pricing and the
**incidents** (who actually scored) for settlement. The reason recorded in 0057
was wrong twice over: the lineups feed is not empty (it returns both elevens for
almost every match), and the missing piece was a market, not data.

## What the lineups feed actually is

`df_li_1_<matchId>` is `~`-grouped exactly like the incidents feed. `LB` opens a
section (`Starting Lineups`, `Substitutes`, `Coaches`), `LC` marks the side
(1 = home, 2 = away), and a player entity carries:

| field | meaning |
|---|---|
| `LI` | name |
| `LP` | player id (the same id the incidents feed puts in `IM`) |
| `LJ` | shirt number |
| `LL` | **lineup slot**, 1 = goalkeeper |
| `LD` | the formation, on the section's first entity (`1-4-3-3`) |
| `LS` / `LR` | the feed's own markers — `Goalkeeper`/`(G)`, `Captain`/`(C)` |

The trap is that **the feed lists a team alphabetically by surname**, so a
player's position *in the feed* says nothing about his position *on the pitch*.
The first dump — `Anderson M., Duke B., Duran R., Gray H., …` under a `1-4-3-3`
— reads exactly like a formation order and a plausible "the last three are the
forwards" story. It is not: it is alphabetical. `Anderson` is the *sixth* slot
(a midfielder) and the goalkeeper is `Gray H.`, alphabetically fourth.

`LL` is what orders an XI and the formation is what splits it into roles. Both
are facts the publisher ships, not our inference.

Corroborated on live feeds: 13 of 16 sampled sides carry the feed's own keeper
marker (`LS÷Goalkeeper` or `LR÷(G)`) and the slot-1 player was that keeper
**13/13**. (The other three sides ship provisional lineups with no marker at
all; the slot still orders them.)

## The model

* **Roles.** An XI is sorted by slot and split by the formation's digits:
  digit 0 is the keeper, digit 1 the defence, the last digit the attack, the
  middle ones midfielders. A shape that omits the keeper (ten digits) is padded;
  an unparseable one falls back to eleven midfielders — a wrong *weight*, never
  a fabricated player.
* **Chances.** `pricing.scorer_probs` gives each starter
  `P = 1 - e^{-share·λ}` where `λ` is the side's expected **remaining** goals —
  the strength model's full-match rate (`pricing.soccer_expected`) scaled by the
  clock — and `share` is the player's role weight over the XI's
  (`SCORER_WEIGHT`: keeper 0.01, defender 0.10, midfielder 0.35, forward 1.00).
  So the list shortens as the clock runs and shortens for the weaker side.
* **Prices.** `pricing.price_independent` gives each leg its own margin
  (`price_market` renormalizes, which is right for an exhaustive book and wrong
  for a list several legs can win at once). The kinds are `scorer-h`/`scorer-a`,
  one list per side, at the sport margin plus 5%.
* **The list.** The four likeliest *distinct* names per side, in-play soccer
  only, and only when the lineups feed gave both elevens.
* **Suspension.** `MIN_SCORER_LAMBDA = 0.2`: once a side has too little of the
  match left to have a list worth quoting, the market is suspended rather than
  quoting the 300.00 noise the collapsing model produces at 90+'. A real board
  suspends the market near the whistle; so does this one.

## Settlement

`settlement.resolve` gained a `scorers` argument and a branch for
`scorer-h`/`scorer-a`: won when the incidents feed has this player scoring, lost
otherwise. It settles on **non-own goals** (an own goal is nobody's) and the
same name on the other side's list does not win.

The server (`Demo._scorers_for`) reads the incidents for the fixture and is
deliberately strict about *absence*: an empty list is a real answer — a goalless
final loses every leg — while a feed that could not be **refreshed**
(`MatchStatsEngine.fresh`) leaves the leg **pending**, never settling a scorer
leg on a snapshot taken before a late goal. The engine's budget is raised from 24
to 36 per window because a live soccer fixture now costs it up to three reads
(stats, lineups, incidents).

## Surfaces

* `stats_engine`: `LINEUPS_KIND`, `parse_lineups`, `lineups()`, `fresh()`,
  `_roles()`, the third entry in `FIELDS`.
* `pricing`: `SCORER_WEIGHT`, `soccer_expected`, `scorer_probs`,
  `price_independent`, the two scorer margins.
* `marketboard`: the `roster` argument and `scorer_lines()`.
* `flashscore_engine`: `_roster_for()` wired into `markets()`.
* `settlement`: `SCORER_KINDS`, the `scorers` argument and its branch.
* `demo/server.py`: `_scorers_for()`, `_settle_verdict` passes `scorers`.
* `web/app/components/SportsHome.jsx`: the two `KIND_LABEL` entries; the extras
  drawer already renders any kind generically.

## Verified

Live board, 32 live soccer fixtures, 6 with a full list in the sample:

```
Envigado 1:0 Barranquilla  (64')
  scorer-h: Tovar A. @28.66, Acuna S. @29.73, Cuervo G. @28.66, Gamboa Valencia J. J. @28.57
  scorer-a: Guerra Navarro S. @26.4, Agamez M. @26.27, Borja S. @26.73, Caballero S. @26.6
Estudiantes L.P. 1:0 San Lorenzo  (34')
  scorer-h: Sosa J. @2.67, Iacovich F. @6.76, Kociubinski B. @6.75, Monsalve M. @6.71
```

The `2.67 → 6.7` gap on Estudiantes is the sole forward against four
midfielders — i.e. the role split doing what it says.

Gates: `frame.selftest` 50/50; `demo.test_demo` 366 tests with only the 6
pre-existing `sqlalchemy` errors; `scripts/verify.py` 0 problems (frontend
rebuilt); 8 new tests — the two parsers, the engine's lineups read and `fresh`,
the board quoting and suspending the list, the settlement verdicts, and the
server's own-goal/side split and pending-on-unread behaviour.

## Not done

* The scorer list is the **starting XI only** — a substitute who scores wins
  nothing, which is what a list over the eleven means. Extending it to the bench
  is a market decision, not a data gap.
* Only the Flashscore board quotes it. Livescore and ESPN carry no lineups feed
  here, so they simply do not offer the market (`roster=None`).
* Pre-match: the XI is published an hour out, but the board only prices it
  in-play, so `_roster_for` only asks for live fixtures — the budget is spent on
  matches that can actually settle.
* The `margin` field `sports_showcase` writes for every market is
  `pricing.overround` (`Σ 1/price − 1`), which is meaningful for an exhaustive
  book and **negative** for a scorer list: four legs of a list where more than
  one can win sum to well under one. It is arithmetically right and the number
  is inert — no surface reads it — but it must not be read as a per-leg margin
  or "fixed" by renormalizing the list, which would price the legs as mutually
  exclusive.
