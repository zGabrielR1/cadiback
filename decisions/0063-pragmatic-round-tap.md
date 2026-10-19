# 0063 — Pragmatic's round settles: the publisher's own saldo is the round

Date: 2026-10-18. Status: **shipped and live-verified** — a real spin through
the deploy settled on our books (see *Live check*; the publisher's saldo, the
tap log, the wallet and the player's activity all agree).

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
* **The answer names its own round, and that is taken first.** A `doSpin`
  answer carries the bet it settled (`c`=coin, `l`=lines — the client's own
  `coin*lines`) and the win (`w`), plus `ntp` (the net). When those fields
  agree with the movement they are the split, exactly, from the first spin of a
  session — a `doInit` or a `reloadBalance.do` carries none of them, which is
  also how a *read* is told from a *round* without trusting the path. The live
  spin below reads `c=0.10&l=20&w=0.00&ntp=-2.00` → stake 200, win 0.
* **The stake is learned from losses as the fallback** (a loss is exactly minus
  the stake; the largest one wins, so a raised bet re-learns it). A round that
  returns part of a learned stake is booked with the learned stake and the net
  as the win (`100/50` for a `-50` movement), which keeps the net exact and only
  moves the stake/payout split — the same bookkeeping caveat 0044 states for PG
  Soft. A raised bet **lowers** the recorded turnover under this rule, never the
  money.
* **A rise with no stake to pair it with is refused.** If an answer moves the
  saldo up but names no round (no `w`) and no bet was ever learned, there is no
  bet to post — a wallet cannot book a bet it cannot name. It is logged
  (`a rise with no stake to pair it with — not settled`) and nothing is posted.
* **The tap is on the round channel only.** Read-only answers (`doInit`,
  `reloadBalance.do`) echo the very balance a round answer already moved, so
  tapping them too would book one round twice — and a read whose answer lands
  after the spin's would even look like a small win. The tap therefore sits on
  the `gameService` path (`/g/<id>/_abs/<host>/gs2c/ge/…`), where every round is
  born, and not on the root paths that only poll the balance.
* **A repeated answer settles nothing.** Idempotency is by construction: the
  same saldo seen twice is not a movement. A client retry, a re-served answer
  or two tabs reporting the same state cannot charge twice (the round id
  `pp-<token12>-<seq>` is the second line of defence, and matches the
  idempotent `settle_rgs_round` the other taps use).
* **A movement no bet could explain is refused, not posted.** A scale or field
  mistake would arrive as an absurd number; the tap caps a single movement at
  the wallet's own per-round bound (R$100,000.00) and logs the refusal.
* **The wallet cannot go negative.** The answers the client reads its own saldo
  from are ours (verified: `balance=5,000.00` where the publisher had
  `100,000.00`), and a spin the player cannot cover is refused by
  `settle_rgs_round` and logged (`refused: WalletError`) rather than posted — so
  a spin the game let through is a round whose money we did not book, never a
  debt.
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

* **A first-round win still needs the named split.** With the fields it is
  exact; without them (an answer that moves the saldo and names no round) a rise
  before any loss is refused and logged, because there is no stake to book it
  against.
* **A round whose win exactly equals the stake (net 0) is not settled.** Net
  zero is also what a replayed answer looks like, and the tap has no round id
  from the publisher to tell them apart; the money is unmoved either way, and
  the row is what is lost.
* **Two tabs on the same title share one token**, so their movements interleave
  into the same state. Each movement still posts once and the net still
  matches; the split can be wrong across the tabs.
* **Trial currency is assumed 1:1 with BRL.** Measured at the publisher for this
  catalog (`100,000.00`), but a title in another trial currency would scale.
* **`mgckey` is not used.** The tap needs no session id of its own — the delta
  is read from the answers we already serve — which is also why it cannot be
  replayed by hand into a wrong wallet.
* **The Painel's dial still applies.** Settlement rides `settle_rgs_round`, so a
  configured win/loss dial steers the payout we post and the row says `biased`
  — intended, and the reason the posted net can differ from the publisher's when
  the dial is on.

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

## Live check — verified

**A real spin, through the deploy, settled on our books** (2026-10-19T01:29Z).

The spin was driven the way the game itself advertises: the HUD says
*"PRESSIONE A TECLA DE ESPAÇO PARA ROTAÇÃO TURBO"*, so a trusted CDP
`Input.dispatchKeyEvent` for **Space** (after clicking the board to focus the
canvas) makes the client send its own `doSpin` — no hand-built body, no guessed
bet. It reads:

    action=doSpin&symbol=vs20olympgate&c=0.1&l=20&sInfo=n&bl=0&index=2&counter=3&repeat=0&mgckey=…

and the answer it got back (ours, after the rewrite):

    tw=0.00&balance=5,000.00&…&c=0.10&sver=5&counter=4&ntp=-2.00&l=20&…&w=0.00

What happened, in three places at once:

* the publisher's own saldo moved `10,000,000 → 9,999,800` minor (their
  `100,000.00` → `99,998.00`, a R$2.00 bet) — the number the tap reads upstream;
* `GET /api/admin/pragmatic-tap` posted
  `stake_minor 200, payout_minor 0, round_id pp-a6cb273a24ec-1, settled: true`;
* the wallet moved `500,000 → 499,800` and the player's activity read
  `rounds_total 1, settled_stake_minor 200` — a `type: "publisher"` round,
  exactly as the other publishers' taps book it.

Also proven live: the client boots to the real board with our saldo in the HUD,
`gameService` answers flow through us, and `doInit`'s publisher saldo reads
`100,000.00` upstream (direct replay) against `5,000.00` on the client's side of
the rewrite — which is the whole evidence for the 1:1 scale.

Covered by tests: 9 in `PragmaticRoundTapTest` (the balance read, the named
split, the fallback, the replay dedupe, the cap refusal, the rise-with-no-stake
refusal, the wallet-less session, the admin log) plus one HTTP-level test in
`ProxyHttpTest` that stubs the publisher and proves the *upstream* saldo is what
moves a real wallet through `settle_rgs_round`.

Still unverified live: a **winning** spin (the named split is what books it, and
it is the one path the test suite has to stand in for) and a **free-spins**
feature (several answers per round). Both are covered by unit tests; neither has
been seen from the deploy.

## Findings this session (not fixed, recorded)

* **`Handler._serve_publisher_root` was defined twice** in `demo/server.py`
  (both from the first deploy commit, `22e55e3`) and Python keeps the *last*
  one — so the richer first copy (`checked_url`, `publisher_query`, 304
  re-fetch, a money-aware `cache_policy`) had never run. The dead copy is now
  removed, and the live one is what serves root paths (its root money answers
  are served `cache="no-cache"` rather than `no-store`; that is the live
  behaviour, untouched). This cost real time: a tap added to the dead copy
  looked wired and did nothing.
* **The free instance is ephemeral.** No persistent disk and a free plan, so a
  spin-down wipes players and in-memory wallet sessions (`unknown player` on the
  next run), and the tap log starts empty. Every live run must mint its session
  inside one warm window — `scripts/live_providers.py`-style harnesses that
  reuse yesterday's token will lie to you.
* **The client hammers a failing root path.** In a 170 s boot the page made
  **7086** `POST /gs2c/saveSettings.do` attempts — the client retries a
  non-200 (its own `RequestManager.StoreResponse`), so those answering badly
  means constant retries. Worth a look on its own; it is a load and stability
  smell, not a money bug.
