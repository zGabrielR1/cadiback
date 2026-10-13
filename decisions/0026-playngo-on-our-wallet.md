# 0026 — Play'n GO on our wallet, no vendor account

Date: 2026-10-12. Status: done (verified live). Newest file wins on conflict.
Follows 0025 (Hacksaw is bindable because its launcher takes `env=`; the rest
were said to need a vendor account — this shows how PGO is done without one).

## Result

**`pgo:book-of-dead` runs on our books, verified live, with no vendor
account.** Driving the real game through our proxy:

- 4 rounds settled: `stake=100 payout=0` ×2 and `stake=100 payout=50` ×2
  (0.5x wins) → wallet `R$372.60 → R$369.60`, exactly the net.
- The rounds land on the ledger with the game's title
  (`pgo:book-of-dead`, "Rich Wilde and the Book of Dead").
- A fresh player with **R$0**: six spin attempts produced **0 round calls**
  and the balance stayed 0 — the game refuses to spin, with
  "Saldo insuficiente — deposite para girar."

## What Play'n GO actually does

- The launcher (`ContainerLauncher`) runs fine **from our origin** — it is
  not like Pragmatic Play's Unity client.
- Its money does **not** travel over HTTP we can read. `configuration/
  prelaunchconfiguration` hands the client
  `"Server": "https://ascflyp.playngonetwork.com/"`, and the game opens a
  **SignalR WebSocket** to `wss://ascflyp.playngonetwork.com//gamehub`
  (`{"protocol":"messagepack"}`).
- Inside that socket is a line protocol: a spin request is
  `1 <credits> <lines> <coin> <flag>` (the stake is the product of the first
  three), and the answer carries `52 <balance> 0 0` — the account balance in
  **minor units**. The initial `52` (login) is the starting balance.

## The approach: tap the page's own socket

We serve the launcher same-origin, so the injected bridge can wrap
`window.WebSocket` **before the game's bundle runs**. It then:

1. Reads the spin line out of the outgoing frame and takes the stake from it.
2. Holds the spin back (with the deposit message) when our saldo cannot
   cover it.
3. Reads the `52` balance line out of the answer, takes the round's **net**
   as the delta from the previous balance, and reports the round to
   `POST /api/wallet/round`, which settles it through the same idempotent
   write the interposed RGS uses (`settle_rgs_round` → `Books.place_bet` +
   `settle_casino`, keyed by round id).

It never touches the publisher's server and never re-encodes a frame: it only
reads what the page already sends and receives, and writes the money to our
books. That is what "intercept server side, run user side" means here.

**Why not a server-side socket proxy?** To rewrite the balance on the wire we
would have to re-encode MessagePack string lengths (the frames are
length-prefixed). Reading the page's socket achieves the same money sync
without touching a byte of the publisher's protocol, which is far less
brittle.

## What this unlocks

- Play'n GO's whole catalog is bindable the same way (the protocol is
  per-vendor, not per-title).
- The same shape should fit other socket publishers (Spribe's SmartFoxServer)
  with their own line/opcode map — the bridge, the wallet endpoint and the
  gating are already generic.

## Caveats

- The in-game credit counter still shows the publisher's demo credits; our
  HUD shows our saldo. Rewriting the wire would fix the cosmetic mismatch at
  the cost of MessagePack re-encoding.
- PGO opens a second socket (`player-events`) that fails harmlessly.
- The stake line's `<credits> <lines> <coin>` interpretation is derived from
  the observed protocol (product matched the balance delta exactly); a title
  with a different bet model would need its line re-checked.
