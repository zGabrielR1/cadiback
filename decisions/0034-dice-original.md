# 0034 — Dados Relâmpago: a whitelabel dice original

Date: 2026-10-12. Status: **shipped** — `frame` 44/44, `demo` 171/171
(+10 dice), `verify.py` 0 problems, export rebuilt, verified live over HTTP.

## 1. Why dice (and what "whitelabel" means here)

The in-house library had Aviator-style games (crash / plinko / mines), slots
and roulette. The missing classic "whitelabel" original is **dice** — the
pure-math, no-publisher-art game every crypto casino ships as an original.
It fills a mechanic we had nowhere (a threshold slider with under/over), its
RTP is a closed form (no paytable to get subtly wrong), and its UI is a slider
and a number.

Alternatives considered and set aside: **Keno** (a full paytable to get exactly
right), **Wheel** (needs a spin visual and a weighted paytable), **Limbo**
(overlaps Crash's target mode). Dice was the smallest, safest, most distinct
addition.

## 2. The engine (`demo/arcade.py`)

Same sha256 discipline as the arcade trio, so `Demo.spin` needed **no new
branch** — `demo:dados` simply joined `ARCADE_GAME_IDS`:

- Draw: `roll = floor(draw_unit * 10000) / 100` → 0.00 … 99.99 (10000 rolls).
- Selection (`selection`): `"under:<T>"` / `"over:<T>"`, `T` ∈ [1.00, 99.00].
- Win chance: `under → round(T·100)/10000`; `over → (10000−round(T·100)−1)/10000`.
- Multiplier (gross return on a win): `HOUSE_KEEP / p` = `0.97 / p`.
- RTP: `p · 0.97/p = 0.97` for **every** selection (97%, minus rounding dust).

A high-probability bet (e.g. `under:99.00`, p=0.99 → 0.98×) pays **below the
stake** even on a win — exactly how real dice works. That is why it settles
through `settle_casino` (arbitrary minor-unit payout), not the odds path.

New functions: `parse_dice_selection`, `dice_win_chance`, `dice_multiplier`,
`dice_roll`, `dice_round`, `dice_rtp`; `arcade_round` and `theoretical_rtp`
gained a `DICE_GAME_ID` branch.

## 3. Wiring

- `demo/server.py`: registered `demo:dados` "Dados Relâmpago" (BR-DEMO-0009,
  RTP 97.00, certified) and added it to `DEMO_CATEGORY` as **Originais** (it
  also lists under Originais because `provider == demo_studio`). The catalog
  emits an empty paytable for arcade ids, as for the trio.
- Front end: new `web/app/components/DicePanel.jsx` (slider 1–99 + Under/Over
  toggle, live **chance % / payment × / potential win**, last-roll readout,
  its own paytable); `page.jsx` owns `diceTarget`/`diceOver` and builds
  `under:<T>` / `over:<T>`; `CasinoHome.tone()` gained a dice case.
- Cover: `scripts/make-covers.py` lists `demo:dados` → `games/demo-dados.svg`
  (and `web/public/games/`).

## 4. Verification

`DiceTest` (10): selection validation; win-chance + multiplier math; RTP 97%
across targets/directions; determinism; a normal win (200 → 388), a sub-stake
win (`under:99.00` → 196) and a loss (0) each settle exactly through the books
with `assert_balanced`; selection required; certified + categorised; a round
lands in history with `unit`. Live HTTP smoke confirmed all of the above, the
`/games/demo-dados.svg` cover, and the 400 on a missing selection.
