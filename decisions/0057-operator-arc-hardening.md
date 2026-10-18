# 0057 — Operator arc hardening: crypto, behaviour control, providers, sports, wheel

Date: 2026-10-17
Status: in progress

## Context

The owner asked for seven things in one arc (verbatim, so nothing is
paraphrased away):

> 1 - Implement cryptocurrency as a valid payment method
> 2 - Implement on the admin panel ways to alter users behaviour on their wins
>     and losses (so we can test how it influences a users actions. We also need
>     to see their saldo in their wallet
> 3 - Fix Asaas implementation: right now it doesnt properly work, since we are
>     using the sandbox keys. I will provide you the real ones for prod and you
>     need/can deploy
> 4 - Fix the sports betting channel: the icons are small, remove the emojis, the
>     options to choose from and bet options are not that big, it should offer
>     more options based on the data of the game (e.g: how many cards, how many
>     faltas, how many goals total, if player X scores. etc)
> 5 - Fix the PG Soft, Pragmatic Play, Spribe, Hacksaw and all other providers
>     wallet proxy: i just tested them live and they didnt work
> 6 - Create a new homemade game, there was one which we would have done but i
>     forgot its name, its just the one easier after dice.
> 7 - And most importantly, create a way for test accounts to have test deposits
>     which influence their wallet.
>
> For 3, do the asaas prod with the keys i give you, but they still havent been
> generated. ... Log what i said in a doc in decisions, and we will take many
> times to make sure every one of these things are working and deployed

A previous run touched these areas but delivered shells, not working features:
the wheel original had an RTP of **137%** (its ladder summed to 13.7/10 while
the comment claimed 9.7), `outcome_bias` was written by the painel but **read by
nothing**, and the Asaas deploy carried no credentials because
`render_deploy.py` reads `.env.asaas` while this machine stores them in
`.env.asaas.sandbox`. The work below keeps the good scaffolding (crypto as a
method name, the painel controls, `WheelPanel`) but makes each item true.

Owner answers that shaped the work:

- crypto → **a real processor (NOWPayments)**, not a notional rail;
- behaviour control → force-win / force-lose / off **and** a win-rate %,
  applied to **publisher games too**, with the wallet saldo shown live;
- sports → **build a stats feed** so cards/faltas/corners can be settled, and
  **attempt scorer props** too;
- new original → **Roda da Sorte (wheel)**, the game 0042 §7 named as next;
- providers → **fix all, Pragmatic Play included** (timeboxed, reported honestly).

## Decision

### 1. Cryptocurrency is a real rail (NOWPayments), config-gated

`demo/crypto.py` mirrors `demo/asaas.py` exactly: stdlib only, injectable
transport, no cross-host redirect, and **the webhook is a hint, never proof** —
a confirmation re-reads the payment from the provider and checks asset + amount
before a centavo posts. `POST /api/deposit/crypto`, `/api/deposit/crypto/status`
and `POST|GET /api/webhooks/crypto`. The cashier shows the asset, receiving
address, amount and polls. While unconfigured the instant demo credit stays,
exactly like the Pix rail. Runbook `docs/crypto.md`.

### 2. Behaviour control is a real controller, and the saldo is visible

`outcome_bias` ∈ {`normal`, `always_win`, `always_lose`, `win_rate`} plus
`win_rate_percent` is read by every in-house settlement (`Demo.spin`: slots,
roulette, arcade originals, wheel). For **publisher** games the publisher owns
the round, so bias scales the payout **we post** — recorded honestly on the
round row (`biased`, `bias_mode`), books balanced either way, never presented as
the game's own result. The painel shows the mode, the slider, and the live
`available_minor`/`bonus_minor` after each action. Persisted as real columns
(new migration + `models.py`), not only JSON.

### 3. Asaas plumbing is fixed; production waits on the key

`demo/asaas.py` and `scripts/render_deploy.py` read the right env file
(`.env.asaas.sandbox` / `.env.asaasprod` / environment). Production is built,
not enabled: when the owner supplies prod keys the swap is a config change plus
a webhook registration plus a deploy.

The resolver picks the first file with a *complete* triple
(`ASAAS_API_KEY` + `ASAAS_CUSTOMER_ID` + `ASAAS_BASE_URL`), so a half-filled
prod file cannot pair a prod customer with a sandbox key. Checked 2026-10-18:
`.env.asaasprod` still has only `ASAAS_CUSTOMER_ID` (the key, secret and base
URL are blank), so the resolver correctly falls through to
`.env.asaas.sandbox` and carries all four settings. The deploy itself is
**blocked this session** on the working tree not being a git checkout (no
remote for `render_deploy.py` to name), not on code.

### 4. Sports: a stats feed, honest count markets, and real icons

New `frame/verticals/sports/stats_engine.py` reads Flashscore's per-match stats
(`df_st_1_<id>`) and incidents (`df_sui_1_<id>`), both cached, budgeted (at most
`DEFAULT_BUDGET` matches per TTL window, so a 160-fixture board cannot ask for
160 stats reads) and fail-open like the fixture engines. Measured stat keys
(2026-10-18, live soccer): ball possession, total/on/off-target shots, corner
kicks, **yellow and red cards**, **fouls**, plus the incidents feed's **scorer
name (`IF`), player id (`IM`), side (`IA`) and minute (`IB`)**.

Markets: the board's existing book (1x2 / moneyline, total, both halves, dupla
chance, ambas marcam, empate-anula, handicap) is joined by **in-play count
markets — cards, corners, fouls over/under — priced from the count so far and
the time left (`pricing.count_over`), with the line moving on the book's own .5
grid as the tally grows**. They are offered **only in-play**, because only then
does the fixture carry the stats that settle them; `settlement.resolve` decides
them from the final match stats and returns *pending* (never a guess) when the
feed is missing. Scorer props are plumbed but **not offered**: the roster comes
from the lineups feed (`df_li_1`), which was empty for the matches seen, so
mirroring the incidents feed alone cannot enumerate a squad — that stays an
honest gap, not a fake market.

The sport tabs get inline **SVG** icons (no emoji, no two-letter glyphs), a
stats panel (possession/shots/corners/cards bars) inside the "mais mercados"
drawer, and larger tabs, selections and odds.

### 5. Provider wallets are verified by a live harness before they are called fixed

`scripts/live_providers.py` funds a player, opens a real wallet session per
catalogued game, fetches the launcher through our proxy and then asks the
question the old byte-count sweep never asked: does **our** wallet answer and
does a real debit land on our ledger? A provider counts as wired only when the
launcher renders (200) *and* `/api/wallet/status` + `/api/wallet/round` move
our saldo. Live run 2026-10-18: **22/22 sampled games wired** across hacksaw,
pg_soft, pragmatic_play, play_n_go and spribe; evolution's launcher returned
502 (upstream `URLError` from this host) though its wallet session itself
answered. The harness states plainly what it does **not** prove — that the
game's own in-page spin calls land here — because RGS-interposed pages live on
the publisher's CDN by design; that final hop needs a browser and is the
deploy-time check. Pragmatic Play is included and passes the harness.

### 6. Roda da Sorte is derived, not typed

The wheel is **100 equal sectors** whose multiplier ladder sums to exactly 97,
so the RTP is **97% by construction** (`wheel_rtp()` returns 0.97 to nine
places, asserted in `WheelTest`); the prior ladder summed to 137%. It is a real
animated SVG wheel (`WheelPanel.jsx`) with honest sub-stake tiers, a cover
(`web/public/games/demo-roda-da-sorte.svg`), cert `BR-DEMO-0011`, and settles
through the same `spin` path as every other original.

### 7. Test deposits are a real, wallet-moving rail

A test account (`is_test`) can deposit from the cashier with no real rail; the
deposit posts as a genuine `deposit` (so wallet, first-deposit and promos react),
tagged `is_test`, behind a setting. The painel credit button posts the same way.

## Acceptance (a session closes an item only when a live check passes)

| # | Item | Done when | Live check |
|---|------|-----------|------------|
| 1 | Crypto | NOWPayments charge → address/QR → provider-confirmed → wallet credited once | deferred until keys |
| 2 | Behaviour | forcing win/lose and a win-rate moves the wallet; painel shows saldo | deploy |
| 3 | Asaas | prod keys → real Pix credits once via webhook | deferred until keys |
| 4 | Sports | cards/faltas/totals/scorer markets render, price and settle; SVG icons | deploy |
| 5 | Providers | each provider's live harness moves our saldo | deploy |
| 6 | Wheel | RTP exactly 97%, playable, settles | deploy |
| 7 | Test deposits | a test account funds itself and the wallet moves | deploy |

## Status

- [x] Decision logged; prior-run leftovers triaged.
- [x] 1 crypto — code + tests (`CryptoTest`, `CryptoDepositTest`); live half awaits NOWPayments keys.
- [x] 2 behaviour — code + tests (`BehaviourTest`); live verify at deploy.
- [ ] 3 asaas — **plumbing fixed** (env-file resolution in `render_deploy.py`); production awaits the owner's keys.
- [x] 4 sports — stats engine + in-play cards/corners/fouls markets + settle + SVG icons + stats panel; tests (`MatchStatsTest`).
- [x] 5 providers — live harness wired 22/22 sampled games (evolution launcher 502); browser hop is the deploy check.
- [x] 6 wheel — exactly 97% RTP; tests (`WheelTest`), cover, SVG panel.
- [x] 7 test deposits — code + tests (`TestDepositTest`).

**Gates (this session):** `frame.selftest` 50/50 · `demo.test_demo` 354 tests
with only the 6 pre-existing `sqlalchemy` (Postgres seam) errors · `verify.py`
0 problems · frontend `npm run build` OK.

**Still open (needs the owner):** Asaas prod keys (§3) — `.env.asaasprod` is
still blank but for the customer id; NOWPayments API key + IPN secret (§1 live);
a browser pass over the deployed provider launchers (§5); and the **deploy**,
which this session could not do because the tree is not a git checkout (there is
no remote for `scripts/render_deploy.py` to name — `--url-only` still reports the
service at `https://cadiback.onrender.com`). `--check` passes 10/10.
