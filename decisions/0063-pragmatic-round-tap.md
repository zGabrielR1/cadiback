# 0063 — Pragmatic's round settles: the publisher's own saldo is the round

Date: 2026-10-18. Status: **built, tested, deployed** — live verification is
one real spin away (see *Live check*; the loader, the rewrite and the field
scale are already proven against the publisher).

Follows 0057 (the correction: Pragmatic was the one working provider whose
rounds reached no ledger), 0043/0044 (PG Soft's display rewrite and its
theater tap), 0060 (Spribe's socket tap), 0062 (the boot fix whose browser
session produced the captures below).

## The gap this closes

Every other working provider settles a round on our books: Hacksaw by RGS
interposition (0025), Play'n GO by the `gamehub` socket tap (0026), Spribe by
the SFS2X socket tap (0060), PG Soft by the trial-wallet reconcile tap (0044).
Pragmatic did not: its `gameService` answers were rewritten so the *client*
showed our saldo, but nothing about the round reached the wallet. A spin at the
counters moved the publisher's demo credits and left our ledger alone.

## What the wire actually says (measured, 2026-10-18)

Captured from a real boot of `pp:gates-of-olympus` through the deploy
(Chromium over CDP, `probes`-free: the captures are in this decision, not a
file).

* **The money call is ours.** The client builds each server call from the URL
  we rewrote, so `POST /g/pp:gates-of-olympus/_abs/demogamesfree.pragmaticplay.net/gs2c/ge/v3/gameService`
  lands on our host and is classified as money (`MONEY_PATHS["pragmatic_play"]`).
  The request body is form-encoded and names the action:
  `action=doInit&symbol=vs20olympgate&cver=442883&index=1&counter=1&repeat=0&mgckey=stylename@generic~SESSION@…`.
* **The answer carries the publisher's own saldo** before our rewrite:
  `…&balance=100,000.00&balance_cash=100,000.00&balance_bonus=0.00&…`. After
  `rewrite_balance` the same field reads `balance=5,000.00` for a player holding
  R$5,000.00 — which is the whole evidence for the scale: **1 unit = R$1, and
  100,000.00 is the publisher's demo opening balance** (a direct replay of
  `doInit` against the publisher, no proxy, returns exactly that).
* **The total is `balance` + `balance_bonus`.** The client's own bundle sums
  them to paint the counter (`XT.GetDouble(Vars.BalanceReceived) +
  XT.GetDouble(Vars.BonusBalanceReceived)`, read out of the served client), so
  the tap must sum them too or a bonus-paid round would look like no movement.
  The bundle spells the field names out: `balance:"balance"`,
  `cashBalance:"balance_cash"`, `bonusBalance:"balance_bonus"`.
* **A spin settles inside one answer.** `doSpin` is the action; the stake is the
  `coin`×`line` the client sends (`data.Fields[coin]=Number(request.Bet)`,
  `data.Fields[line]=Number(request.Line)`, and the client's own net position
  moves by `coin*lines`), which is why a full loss at the minimum bet reads as
  exactly 100 minor units.

## Why the tap is server side, not in the bridge

The bridge runs *in the page*, and the page sees our rewrite: by the time a
`gameService` answer reaches the client, `balance` is **our** saldo. A bridge
tap would therefore watch a constant and settle nothing. The publisher's number
exists in exactly one place — the upstream body in the serve path, before
`rewrite_balance` — so that is where the tap reads it. (PG Soft's bridge tap is
the opposite case for a real reason: PG's money calls bypass us entirely, so
there the page is the only witness. The rule is *read the publisher's own
number wherever it is still the publisher's*, not "taps live in the bridge".)

## What it does (`Demo.pragmatic_note_balance`)

* **The movement is the round.** The first saldo of a session is the baseline;
  every later answer whose saldo differs posts one round: a drop is the stake
  going out, a rise is what came back. `payout - stake` is **always** the
  publisher's own net movement, which is the only invariant the books can
  honestly keep — the round itself is drawn server side and cannot be re-cut
  from outside (0044's finding, still true).
* **The stake is learned from losses** (a loss is exactly minus the stake; the
  largest one wins, so a raised bet re-learns it). A round that returns part of
  a learned stake is booked with the learned stake and the net as the win
  (`100/50` for a `-50` movement), which keeps the net exact and only moves the
  stake/payout split — the same bookkeeping caveat 0044 states for PG Soft.
  A raised bet **lowers** the recorded turnover under this rule, never the money.
* **A repeated answer settles nothing.** Idempotency is by construction: the
  same saldo seen twice is not a movement. A client retry, a re-served answer
  or two tabs reporting the same state cannot charge twice (the round id
  `pp-<token12>-<seq>` is the second line of defence, and matches the
  idempotent `settle_rgs_round` the other taps use).
* **A movement no bet could explain is refused, not posted.** A scale or field
  mistake would arrive as an absurd number; the tap caps a single movement at
  the wallet's own per-round bound (R$100,000.00) and logs the refusal.
* **The R$0 gate comes free.** The client gates its own spin on the balance it
  was given, and what it was given is our saldo — a player with nothing cannot
  spin at the counters, and no separate gate is needed.
* **Settlement rides `settle_rgs_round`.** Same write, same row shape
  (`type: "publisher"`, the game's title, the bias dial applied to the payout we
  post), so the Painel and `/api/history` show Pragmatic rounds exactly as they
  show the other publishers'. If the dial is set, the posted win is steered and
  the row says so — the tap does not add a second bias path.

## What the tap saw (`GET /api/admin/pragmatic-tap`, admin only)

A 40-entry ring buffer, newest first, one line per answer: the timestamp, the
game, the token's first 8 characters (never the whole token), the publisher's
saldo, the delta, and what was done with it (`baseline`, `no movement`,
`settled`, `above the per-movement cap — not settled`, `refused: <error>`).
A money tap is invisible in production otherwise, and "was it us or was it the
publisher" is the first question worth asking.

## Limits, stated plainly

* **The first round of a session can mis-price the stake.** Before any loss is
  seen there is no stake to learn from, so a winning first round books as a
  pure win (stake 0) — the net is still exact. A partial win reads as a smaller
  stake until a full loss re-learns the real one.
* **Two tabs on the same title share one token**, so their movements interleave
  into one delta stream. Each movement still posts once and the net still
  matches; the split can be wrong across the tabs.
* **Trial currency is assumed 1:1 with BRL.** Measured at the publisher for this
  catalog (`100,000.00`), but a title in another trial currency would scale.
* **`mgckey` is not used.** The tap needs no session id of its own — the delta
  is read from the answers we already serve — which is also why it cannot be
  replayed by hand into a wrong wallet.

## Traps that cost time (all measured)

1. **A malformed hand-replayed spin freezes the publisher's demo session.**
   Replaying `action=doSpin&c=1&l=20` directly against the publisher answered
   `200 frozen=Internal server error. The game will be restarted.&msg_code=11&ext_code=SystemError`
   — and that session then **stalled at the splash** on the next page load with
   the same browser profile (the profile's cookie kept it). A fresh
   `--user-data-dir` boots again. Do not hand-replay a spin into the profile you
   are about to verify with.
2. **`Emulation.setUserAgentOverride` breaks the boot.** The 0062 session pin
   pins the two environment readings the bundle harvested (the user agent among
   them), so overriding the UA leaves the loader on its splash with zero
   `gameService` calls. The harvested UA (`HeadlessChrome/156…`) is the one that
   works.
3. **The live instance drops its state.** The test account minted for the
   capture was gone minutes later (`unknown player`), and `GET
   /api/admin/test-accounts` was empty — the container had restarted. Re-mint
   before every live run; never assume yesterday's token.

## Live check

Proven live on the deploy this session: the client boots to the real board with
our saldo in the HUD, `gameService` answers flow through us, `doInit`'s
publisher saldo reads `100,000.00` unmodified upstream (direct replay) and
`5,000.00` on the client's side of the rewrite. The tap itself is covered by
8 unit tests and 1 HTTP-level test that stubs the publisher and asserts the
*upstream* saldo is what moves a real wallet through `settle_rgs_round`.

Still owed by a human: **one spin at the counters**. It should post a
`type: "publisher"` round in `/api/history` and move the saldo by the net;
`GET /api/admin/pragmatic-tap` will show the movement and what was done with it.
