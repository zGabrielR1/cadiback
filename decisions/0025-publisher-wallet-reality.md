# 0025 — provider games on our wallet: what actually works

Date: 2026-10-12. Status: done (Hacksaw verified live; others explained).
Newest file wins on conflict. Companion to 0022 (the mechanism) and 0024 (the
perspective).

## Result

**`hs:rip-city-dice` (Hacksaw Gaming) runs on our books, verified live.**
Driven through `/g/hs:rip-city-dice/?env=<ours>&token=<ours>` with a real
wallet token:

- 34 spins clicked in the game → balance `R$342.00 → R$305.20`.
- 20 publisher rounds recorded, **3 with a payout** — e.g. a
  `stake=200 payout=100 (0.50x)` round credited our ledger (a payout below
  the stake, which the odds-based settlement cannot express).
- Every spin hit our RGS (`/rgs/hacksaw_gaming/api/play/bet`); the saldo the
  game shows is ours.

Mechanism (decision 0022): Hacksaw's **free-play launcher takes its RGS base
from the `env=` query parameter**, so the game is pointed at our
`/rgs/hacksaw_gaming/api`, our backend forwards each call to Hacksaw
server-to-server, and the stake/win settle through `frame` (`wallet_debit` /
`wallet_credit` / `Books.settle_casino`). The balance the RGS reports is
replaced with the player's.

## The fix this session

`game_proxy.rewrite_urls` now rewrites **only the provider's money URLs**,
not every publisher URL. Previously it moved the whole game (client,
bundles, JSON, art) onto our origin; the Unity importer then deserialized an
**empty game root** (`GameRoot.children.len=0`) — a load-order sensitivity of
its loader, not bad bytes (the resources are byte-identical through the
proxy; the direct page also loads them with 0 errors). With assets left on
the publisher's CDN (which sends `access-control-allow-origin: *`), the game
now gets past that blocker.

The previous session's byte-patching of the Unity client (`diag`, `tdeser`,
`pcf`, `wca`, the `Transform.prototype.deserialize` / `resolveReference`
wrappers) was removed: it was largely dead code (the wrappers were
overwritten by the bundle's own later assignments) and only the URL rewrite
was ever load-bearing.

## Why the rest still cannot be bound

A publisher's client is built to run **on the publisher's own origin**. Serve
it from ours and it breaks:

| Provider | Client | Result from our origin |
|----------|--------|------------------------|
| Hacksaw | HTML5, takes `env=` | **runs** (verified above) |
| Pragmatic Play | Unity (custom JS importer) | renders on its own origin; from ours the importer stalls (empty game root → animation-curve error) |
| Spribe | Angular + SmartFoxServer socket | loads, stalls on the socket |
| Play'n GO | bundle + `window.serverUrl` | loads, stalls |
| PG Soft | static CDN | unreachable (DNS) |

Each vendor's *real* wallet integration is an **operator account with that
vendor**, which the client picks up from a server-issued config:

- Play'n GO: `window.serverUrl` in the launcher shell.
- Spribe: the page takes `operator=<id>` + a backend-minted `token`.
- Pragmatic Play: the RGS host comes from PP's `openGame.do`, not from a
  parameter.

Only Hacksaw's *demo* exposes a redirectable RGS (`env=`) for free play.
Binding the others needs the vendor's operator/SEAMLESS contract — the
commercial track retired in decision 0007.

## Hacksaw expansion (2026-10-12)

- The catalog ships **139 Hacksaw titles** (`hs:*`), up from 1. They are real
  free-play demos discovered from the publisher's own games page
  (`data-gameid`) plus each game's `version.json` — the same way Hacksaw's own
  launcher resolves the build —
  and each was verified before shipping: launcher 200 and RGS `gameInfo` 200.
- The wallet binding is generic (`env=` interposition, no per-title work), so
  every one of them settles on our books. Verified live on `hs:chaos-crew`
  (gameid 1059): 30 bets through `/rgs/hacksaw_gaming/…`, 20 rounds on the
  books, 4 with a payout (incl. a 0.30x), wallet moved.
- Reproducible: `python scripts/discover_hacksaw_demos.py [--write]`. Covers:
  `python scripts/make-covers.py`, then rebuild `web/`.
- 12 publisher-listed titles are skipped (Dice, Plinko, Limbo, Hi-Lo, Wheel,
  Baccarat, Twenty-One, Blocks, Lines, Colors, Speed Crash, Moneyplane):
  their RGS `gameInfo` refuses the demo query, so they are not shipped.
- The catalog is now 178 publisher demos (139 Hacksaw, 22 Pragmatic Play,
  8 Spribe, 5 Play'n GO, 2 Evolution, 2 PG Soft) + 6 in-house titles.

## What this means

- Every Hacksaw title is bindable with the same integration (the catalog
  carries one, `hs:rip-city-dice`; adding siblings is catalog work, not
  integration work).
- The other 39 publisher demos stay **wallet-isolated free play** (honest:
  they run on the publisher's demo credits) until a vendor operator account
  exists.
- The in-house titles (`demo:*`, 6) remain the wallet-settled originals.
