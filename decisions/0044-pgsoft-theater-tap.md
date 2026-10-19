# 0044 — PG Soft theater tap: settle the trial-wallet delta on our books

Status: **live-verified (0064, 2026-10-19).** Same pattern as the Spribe
theater bridge and the Play'n GO socket tap: read what the page already says,
touch nothing of the publisher's. The live path differs from the original
cross-origin poll: when the launch is steered same-origin the server keeps the
`dt.tk` from the handshake and `GET /api/pg/wallet` polls the trial wallet
unrewritten. See 0064 for the evidence and for the production caveat.

## Why a tap, not an interposition

The user's spin capture (`probes/pg-spin.json`, 17 real spins) settled
the protocol question: every `game-api` request AND answer is opaque
encrypted bytes (fully different bytes per spin, no plaintext fields,
no balance doubles, not zlib). There is no spin to re-encode and no win
to read. Building spins server-side would mean breaking the message
encryption — not this project.

But two things on the wire are plaintext:

- `verifySession`: form in, JSON out, carrying `dt.tk` (access token).
- `GameWallet/Get`: form in, JSON out, carrying `dt.cb/tb` (trial
  balances in game-currency units, 1 unit = R$1 in the BR trial).

So the tap reconciles instead of interposing: after every Spin, read
the trial wallet through the publisher's own endpoint and settle its
delta on our books via the existing `/wallet/round`
(`settle_rgs_round`, idempotent per round id).

## How it works (all in the injected bridge, `game_proxy._BRIDGE`)

- Harvest `tk` off the verifySession answer (fetch/XHR hooks, response
  cloned, page untouched) + the api origin off its URL.
- After a Spin resolves, poll the trial wallet until it stills (800ms,
  up to 12s): first move settles with the stake, trailing moves
  (respin features) settle as pure wins. Serialized per launch.
- Stakes are learned from losses (a loss is exactly -stake; kept as the
  max). The settled BALANCE is always exact; the stake/payout split is
  bookkeeping around it (a partial win settles with an equivalent net).
  Bet decreases below the learned stake overstate turnover, never money.
- `bet_url: /v4/Spin` arms the bridge's R$0 gate for PG: no spin leaves
  the client when our books are below the minimum. Without a login the
  report 401s and drops silently — free play stays free play.
- `pg_gi` (from the catalog row) names the game in the wallet poll.

One tap covers all 92 PG titles: same client core, same endpoint shape
(`game-api/<slug>/v4/Spin`), per-slug URLs matched, never enumerated.

## Honest limits

- Boot through our origin now works (gi-rooted launches + the full
  launcher query, 0043): the remaining live verification is one human
  spin on the deployed site, which should settle on the books via this
  tap and show in `/api/history` + the Painel.
- Trial currency 1:1 with BRL is the BR-trial convention as measured
  (100000.00 demo credits); a currency mismatch would scale every
  settlement and has to be re-checked per title on first live spin.
- Server-side wallet polling was PROVEN DEAD first: same-mint `tk` +
  proper Origin/Referer still answers 3005 — the wallet only exists
  after the binary game init, which only the real client performs.
