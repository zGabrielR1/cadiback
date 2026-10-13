# 0031 — Spribe on our wallet via the operator channel (Aviator settles)

Date: 2026-10-12. Status: **shipped and verified with real bets** —
R$100 → R$1 bet → cashout 1.28x → **R$100.28** on our books, round row
`spribe:aviator stake=100 payout=128` in history; a bust settles the
stake as a loss; an R$0 player's trial bets mirror nothing.
`frame` 44/44, `demo` 153/153 (+2 theater), `verify.py` 0 problems.

## How (no socket decoding)

The client already reports everything to its operator over
`parent.postMessage` when framed (decoded from the bundle, captured live
with a real bet + cashout):

- game → us: `ifc.init {balance:50000, currency:BRL, precision:2}`,
  `ifc.make.bet {id, amount}`, `ifc.make.bet.complete {id, code}`,
  `ifc.cashout {id}`, `ifc.update.balance {amount}`,
  `ifc.win.info {id, amount}` (gross, major units),
  `ifc.cashout.complete {id, code}`, `ifc.start/end.round`,
  `ifc.update.stake`. A R$1 bet cashed at 1.13x reported
  `win.info {id:1, amount:1.13}` against `update.balance 50000.13`.
- us → game: `{cmd:'ifc.set.balance', data:{value}}` (major units),
  consumed by `userService.balance`.

`GameTheater.jsx` (`useSpribeBridge`, Spribe rows only, same-origin
messages only) mirrors each round through the existing idempotent
`POST /api/wallet/round`: `make.bet` opens the round, `win.info`
settles it with the gross payout, `end.round` settles still-open bets
as 0 after a 2s grace (a last-instant cashout's `win.info` lands first),
`cancel.bet` / non-200 drops the round untouched. `page.jsx` passes the
wallet token through (`officialToken`, refreshed on quick-switch).

## The R$0 gate (theater-side, by necessity)

The demo ships `isBalanceValidationEnabled=false`, so the game client
never refuses — the gate lives in the theater: a bet our spendable
(`available + bonus`) cannot cover is marked ignored, runs on trial
credits only with an on-screen notice, and is never mirrored (verified:
R$0 player fired trial bets, zero new book rounds). `place_bet`'s
insufficient-balance refusal stands behind as a second wall — the books
cannot overdraw even on a race.

Two execution-caught bugs, both fixed: the first balance push sent
`NaN` (page profile carries `available_minor`, not `balance_minor` —
bets were silently refused); the message listener closed over a stale
profile (now mirrored through a ref).

## Scope

Aviator verified end to end. The other 7 Spribe minis speak the same
`ifc` channel (same client family) but were not individually bet-tested;
`GameTheater` applies the bridge to every `spribe:` row.
