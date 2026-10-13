# 0032 — Crash Nitro: interactive live cash-out (manual mode)

Date: 2026-10-12. Status: **shipped** — `frame` 44/44, `demo` 161/161
(+8 live-crash), `verify.py` 0 problems, export rebuilt, verified live over
HTTP (start hides the bust; poll climbs; cash-out pays; twelve rounds
busted and settled as losses into the ledger).

## 1. The ask

The crash original only let the player *name* a cash-out multiplier up
front (`2.00x`) and the round settled instantly against it. The owner
wanted the **primary** way to play to be interactive: a live curve the
player watches, and a click that cashes out at whatever multiplier the
curve is showing at that instant.

## 2. Design: one draw, two modes

`demo:crash-nitro` now has two modes sharing one engine and one RTP:

- **Target (auto)** — unchanged: the player names a cash-out `T`
  (`selection`), a win pays `stake * T` (`demo/arcade.crash_round`).
- **Live (manual, new default)** — the player watches the curve climb and
  cashes out at any instant. The curve is
  `multiplier(t) = exp(CRASH_GROWTH_PER_SEC * t)`; the round is a win if
  `bust >= multiplier(t)` and pays `stake * multiplier(t)`, capped at
  `CRASH_LIVE_MAX` (1000x).

Both draw the bust from the same `crash_point_from_unit(unit)` (the 3%
instant bust at 1.00x included), so cashing out at a fixed multiplier `m`
wins with probability `P(bust >= m)` — the RTP is the same **97%** in
both modes for every stopping rule (`crash_live_rtp`, exact over the
100000-value grid). Added in `demo/arcade.py`: `crash_multiplier_at`,
`crash_elapsed_for`, `crash_bust_multiplier`, `crash_live_round`,
`crash_live_rtp`.

## 3. The bust must stay secret

The bust is `sha256(game_id:round_id)`, so revealing the seed before the
curb settles would let a client compute it and cash out one tick early
every time. The live round therefore:

- draws a **secret** `round_id` (the seed) server-side and never sends it
  until the round settles; the client gets an opaque `token` handle;
- returns only the curve parameters (`started_at`, `server_now`,
  `growth`, `max_multiplier`) at start;
- reveals the bust only in the settle response, after the money moved.

The server's clock is authoritative: the payout multiplier is computed
from `now - started_at` when the cash-out request arrives, or from the
poll/sweep once the curve is past the bust.

## 4. Endpoints and the round lifecycle

`POST /api/crash/start` draws the hidden bust, debits the stake
(`place_bet`, one live round per player), persists the in-flight round to
`crash_pending.json`, and hands back the token + curve.
`POST /api/crash/status` is the client's ~300ms poll: `flying` with the
current multiplier, or `busted` (settles the loss and reveals the bust).
`POST /api/crash/cashout` settles at the server's instant. Settlement is
`settle_casino` with the exact payout, so partial returns and the bonus
split behave as in the target mode.

A round the client abandons (tab closed) is drained by `sweep_crash()`,
called from the periodic `settle_pending()` paths and the heartbeat
thread: past the bust point it settles as a loss. A round still pending
at **boot** was debited but never settled, and since we cannot know
whether the player had cashed out first, boot finishes it as a
**cancelled** round — the stake is returned and the row is recorded — so
a restart can never strand money in `bet:staked`.

## 5. Front end

`web/app/components/CrashPanel.jsx` gains a **Manual / Automático**
toggle. Manual (default) animates the curve locally from the returned
curve parameters, polls for the bust, and turns the primary button into
`SACAR {mult}x · R$…`; the plane's tip turns red on a bust and green on a
cash-out. `page.jsx` passes `player`, `onRefresh` and `onNeedAccount`.
