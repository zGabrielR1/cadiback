# 0022 — publisher games on our books (wallet synchronisation)

Date: 2026-10-10. Status: decided. Newest file wins on conflict. Replaces the
earlier (wrong) "in-house flagship originals" note.

## Objective

Every casino title in the lobby is a **publisher's** game. The lobby does not
sell our own titles. The publisher's game must draw its balance and its payouts
from **our** server wallet: with R$0 in our books the player can look at the
game but cannot spin, and gets a "deposit to play" message.

## The one hard constraint

A publisher free-play demo has **no wallet callback** — its balance and round
outcomes live on the publisher's own RGS (recon, decision 0020). So the game
cannot be told to use our wallet by configuration alone. To put it on our books
we place **our own layer in front of the game's money calls**: the game's client
stays the publisher's, but the calls it makes for balance / stake / win are
answered by our server, which is where `Books` lives.

## Architecture

```
  player ──▶ web (launch)  ──▶ /api/wallet/launch   (token bound to player+game)
                                     │
  publisher client (iframe) ──▶ interception layer  ──▶ /api/wallet/{debit,credit}
                                     │                        │
                                our server, same origin   frame/wallet/books.py
```

1. **Launch token** — `POST /api/wallet/launch` binds a session to one
   (player, game) and answers `can_play` from the real saldo. This is built.
2. **Operator wallet API** — `POST /api/wallet/debit` takes the stake
   (refused with a deposit message when short), `POST /api/wallet/credit`
   settles the win. Both post through the double-entry books; `GET
   /api/wallet/status` reports the live balance. Built.
3. **Arbitrary-payout settlement** — `Books.settle_casino(key, player, stake,
   payout, bonus_part)`: a publisher round can pay less than the stake (a 0.42x
   win is still a win), which the odds-based `settle_bet_win` cannot express.
   Built, tested in `frame/tests/test_frame.py`.
4. **Interception layer (built)** — the piece that makes the publisher client
   actually call 1–2. Two shapes, per publisher (see below): RGS interposition
   (`demo/rgs_proxy.py`, Hacksaw) or a same-origin page proxy
   (`demo/game_proxy.py`, Pragmatic Play). Websocket publishers (Spribe
   SmartFoxServer, PGO) still need a websocket proxy on top.

## Two routes, chosen per publisher

1. **RGS interposition (preferred)** — some launchers take their RGS base from
   an `env=` parameter (Hacksaw). The launcher's own money calls are then
   pointed at us and answered from our books; the page and its assets stay the
   publisher's. No asset proxying. This is the publisher's own operator
   integration, and it is what `demo/rgs_proxy.py` implements. **Built and
   verified live — money moves both ways (see Status).**
2. **Page proxy** — a publisher without such a parameter (Pragmatic Play) needs
   the whole page served from our origin (`demo/game_proxy.py`), which is what
   puts its client same-origin with our RGS.

A publisher hosted on its own public HTTPS page cannot call a *local* RGS
directly: the browser refuses a public page reaching a private address. So the
launcher is served from our origin in route 1 too (`/g/<id>/?…`), which also
removes CORS from the picture; in a real deployment (public operator, public
RGS) the calls would work straight from the publisher's page.

## What this rules out

- Selling our own in-house titles in the casino: gone (owner, 2026-10-10).
- Config-only "use our wallet": impossible, there is no callback.
- Real third-party titles with genuine vendor wallet delegation: still a
  licensed integration (retired track 0007), not this.

## Status

- Undone: the in-house flagship originals (`demo:gates-of-olympus`,
  `demo:aviator`), their panels and engines, and this file's predecessor.
- Built and green:
  - launch token (`POST /api/wallet/launch`), operator wallet API
    (`/api/wallet/{status,debit,credit}`), arbitrary-payout settlement
    (`Books.settle_casino`);
  - **RGS interposition** `demo/rgs_proxy.py` and its `/rgs/<provider>/…`
    routes, plus `settle_rgs_round`: the launcher is served from our origin
    with its `env=` and `token=` swapped for ours, the first call binds the
    RGS session id to the wallet, each round's stake is debited and its
    accumulating win credited when the RGS finishes it, the saldo the client
    shows is ours, and a stake the wallet cannot cover is **refused** with
    "Saldo insuficiente — deposite para girar." rather than played on the
    publisher's demo credits.
    **Verified live against Hacksaw (RIP City Dice)**: the game boots through
    our RGS (`authenticate`, `meta/gameInfo`, `play/gameLaunch`, `play/bet`),
    twelve spins took the wallet from R$20.00 to R$1.00 (wins credited — a
    0.30x round settled as `stake 200 payout 60`), and the next spin was
    refused with the wallet untouched.
  - **same-origin game proxy** `demo/game_proxy.py` and its `/g/<game_id>`
    routes: the launcher and every asset/RGS request are forwarded, every
    publisher URL is rewritten to an absolute URL on our origin (relative
    rewriting broke the client's own URL parser, which splits on `//`),
    the bridge (`/g/bridge.js`) is injected into the launcher, and a
    cookie-bound catch-all serves the root-level paths a spawned client asks
    for.
  - front end launches publisher games through `/g/<game_id>?token=…`
    (`page.jsx` mints the token and prefers `interposed_url`).
- **Open item — Pragmatic Play's Unity client (next session).** The game boots
  through the proxy, same-origin, with our saldo in the HUD and every asset
  byte-identical, but its loader stalls at ~72%: the Unity importer finishes
  the JSON sections and then cannot find its `LocalizationRoot`
  (`internalContinueImporting` → `ret.objects[JsonTypes.indexOf(0)]
  .GetComponentsInChildren(LocalizationRoot,true)[0].transform`). Every bundle
  request returns 200 and none is corrupted, so it is an importer
  ordering/timing sensitivity under the proxy, not bad data. Pick this up next.
  **Root cause found (2026-10-11).** The Unity importer only pushes the
  *first* root object of each JSON resource into `rootObjects`
  (`if(resIdx==0&&goIdx==0)this.rootObjects.push(...)`), so
  `ret.objects` holds a single root per bundle. In the GAME bundle the
  first root is `GameRoot` — an empty shell whose Transform parent is
  `fileID` 0 — while the tree that actually carries `LocalizationRoot`
  hangs off a *sibling* root (`XTRoot` → `Root` → `LocalizationRoot`,
  `Root`'s parent is `XTRoot`, `fileID` 12). `GetComponentsInChildren`
  only walks `transform.children`, so searching from `GameRoot` finds
  nothing and the original line throws "Cannot read properties of
  undefined (reading 'transform')". Three fixes applied in
  `game_proxy.rewrite_urls` (build.js is text-patched at serve time):
  (1) push *every* root object of every resource into `rootObjects`;
  (2) in `internalContinueImporting`, search all `ret.objects` for the
  one carrying `LocalizationRoot` instead of only
  `ret.objects[JsonTypes.indexOf(0)]`; (3) add every `ret.object` as a
  scene root (`globalRuntime.addNewSceneRoot` in a loop) so the GUI
  bundle's roots — re-parented under the LocalizationRoot transform —
  are reachable from `globalRuntime.sceneRoots` (this fixed a later
  `TournamentSimpleOptIn` "Cannot set properties of undefined" in
  `logo_info.js`). After (1)+(3) the `LocalizationRoot` error and the
  `TournamentSimpleOptIn` error are both gone and the importer completes
  ("Loaded 11571 gameobjects"). **Remaining (2026-10-11):** with all
  three fixes the loader still stalls at the ~60-70% bar; the next
  error is `Cannot read properties of undefined (reading 'x')` in
  `UHTMath.Vector3.scale`, reached from `UISprite.Start` →
  `SetSpriteName` → `Collider.UpdateCachedMembers` →
  `Transform.transformPoint` → `Transform.rotation` →
  `Transform._internal_get_scale` → `Vector3.scale`. A transform's
  scale/rotation is undefined at sprite init — the next thing to chase.
  Note: fix (2) was momentarily lost when fix (3) was added (the edit
  replaced fix 2's block); re-added. Test harness: `cap/pp-long.cjs`
  (60 s console+pageerror capture), `cap/pp-stack.cjs` (pageerror
  stack only), `cap/pp-final.cjs` (info+screenshot). Server:
  `cap/serve.py` on :8796.
- Websocket publishers (Spribe SmartFoxServer, Play'n GO) additionally need a
  websocket proxy.
- Deferred: deleting the in-house slots/roulette library so every lobby title is
  a publisher's — done once the money-tap is live, so the lobby is not left
  without a wallet-settled game.
