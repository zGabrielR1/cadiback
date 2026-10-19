# 0064 — A browser that runs here, and PG's money calls routed same-origin

Date: 2026-10-19. Status: **shipped; Pragmatic win and PG Soft spins
live-verified.** The PG production caveat is recorded under *Limits* — this
decision does not claim the Render origin can reach PG's api host.

Follows 0043/0044 (PG's display rewrite and the trial-wallet tap), 0055/0062
(the provider session boot fixes), 0063 (Pragmatic's saldo movement).

## Context

Live verification had been driven from a Linux Chromium AppImage. That cannot
run on this machine, so the evidence pipeline had no working browser. Two
independent problems had to be solved before a spin could be believed:

1. **The driver.** A real browser, real trusted input, and a verdict read from
   the wire and the books — not from the page's own claim.
2. **PG Soft's CORS wall.** Its api host answers `verifySession` with
   `access-control-allow-origin` only when the origin is `*.pg-demo.com`.
   `http://127.0.0.1:*`, `localhost` and `https://cadiback.onrender.com` get no
   such header, so the client dies at the splash even though our wallet HUD
   renders.

## Decision

### The harness

`scripts/drive_game.mjs` drives the installed Chrome/Edge over the DevTools
Protocol using Node's global `WebSocket` — no Playwright, no AppImage. It
navigates, waits for a real canvas, sends `Input.dispatchMouseEvent` /
`Input.dispatchKeyEvent` (the same events a hand produces), captures
network/console, screenshots, and reports. Useful flags added while proving the
providers:

| flag | why |
|------|-----|
| `--start x,y` | one trusted click after boot, for a splash's INICIAR button (PG). `--tap` repeats per press and is the wrong tool. |
| `--boot ms` | a canvas with size is not a playable board; PG spends ~8 s at "A iniciar sessão". |
| `--bodies` | fetch plaintext response bodies (handshake, trial wallet) after the run. |
| `--eval js` | read a final page fact (tap counters) once the presses are done. |
| `--ignore-cert-errors`, `--host-resolver-rules` | local TLS and host mapping, below. |

`scripts/live_spin.py` wraps it: in-process `Demo` + server, a depositing
player, a minted launch, the driver, then a verdict from the wallet, the
publisher round rows and the provider's own tap.

**TLS is a real requirement, not a preference.** Pragmatic's Unity client
hardcodes `https://` in front of the document host; a plain-HTTP local run is
an unreachable TLS target. `--tls` mints a throwaway self-signed cert (SANs:
`localhost`, `127.0.0.1`, the requested host) in a temp directory.

**Host mapping is test-only.** PG will not lay out under the headless UA, and
its money host only allows `*.pg-demo.com`. The local check therefore serves
the page under a `pg-demo.com` name that Chrome resolves to loopback. Nothing
about it ships.

### PG Soft: steer the money host, then own the token

Measured on 2026-10-19:

* `POST https://api.<label>.com/web-api/auth/session/v2/verifySession` with
  `Origin: https://public.pg-demo.com` (or `https://www.pg-demo.com`) echoes
  the origin in `access-control-allow-origin`; with `http://127.0.0.1:PORT`
  or `https://cadiback.onrender.com` the header is absent and the browser
  reports `net::ERR_FAILED`. Measured in `probes/pg-win-check.json`.
* The launch's mangled `ao` is not used verbatim: the client takes the
  registrable domain and prefixes `api.` (`ao=demo.pg-demo.com` →
  `https://api.pg-demo.com`). Therefore **steering only lands on our server
  when the document itself is served from that same `api.<registrable>`
  host.** `live_spin.py --steer` refuses any other combination instead of
  producing a confusing splash.

With `--host api.pg-demo.com --tls --steer`:

1. `PG_AO_HOST` is set to `api.pg-demo.com:<port>`; the launch carries it in
   `ao`.
2. The client sends `verifySession`, `GameName/Get`, `GameInfo/Get`,
   `GameWallet/Get` and `Spin` to the same origin as the document.
3. `Handler._serve_publisher_root` forwards root `/web-api/…` and
   `/game-api/…` to the api host its PG session minted — **not** the document
   host, which 404s those paths — with `Origin`/`Referer` reset to the
   launcher's own origin.
4. `Authorization` joins `game_proxy.FORWARDED_HEADERS`. PG's `game-api`
   answers 401 without it (measured: forwarding it turned `GameInfo/Get` 401
   into 200 and let the spin through).
5. `pg_proxy.note_access` records `dt.tk` from the `verifySession` answer that
   came through us. Only the server can read it at this point.
6. `GET /api/pg/wallet` polls the publisher's trial wallet with that token and
   `gid`, and returns `cb` **without** the display rewrite. The bridge's tap
   polls this same-origin endpoint.

The last point matters: the client's own `GameWallet/Get` is rewritten to the
player's saldo (that is the theater). If the tap polled the rewritten answer it
would only ever see our constant. The tap needs the publisher's untouched
movement, and the server is now the one place that has both the token and the
unrewritten body.

## Live check

```
python scripts/live_spin.py --game pp:gates-of-olympus \
    --press 40 --gap 3000 --settle 14000 --wait 45000 --tls
# → 4 rounds, one stake=200 payout=300, wallet 500000 → 499500

python scripts/live_spin.py --game pg:fortune-tiger \
    --start 640,624 --tap -1,717 --tap-only --press 3 --gap 3500 \
    --settle 16000 --wait 40000 --boot 10000 --tls \
    --host api.pg-demo.com --steer
# → 2 rounds stake=300 payout=0, wallet 500000 → 499400,
#   HUD R$ 4.994,00; /v4/Spin 200, /api/wallet/round 200
```

`--tap x,y` is **canvas-relative** (the canvas is re-measured at tap time).
PG's splash canvas is full-page, but the board's canvas is a 450×800 portrait
at `x=415`, so the spin button's page centre `(640,717)` is `x=225` relative
to it — `-1` means "canvas centre" and is the stable spelling. `--tap-only`
uses the click as the spin input instead of Space; the keyboard path proved
flaky on a board that had just finished its entry animation. The driver's
report and screenshot land in `probes/live-spin.json` and
`probes/live-spin.png`.

The 8-spin follow-up caught partial wins (`stake 300 / payout 180`) and seven
settled rounds for eight spins — the limitation below, observed rather than
assumed.

## Limits (recorded, not hidden)

* **Production PG still needs same-origin money routing.** The Render origin
  cannot be the document's host at `api.<registrable>`, so the client cannot
  be steered there by this trick alone. Serving PG through a domain we control
  at that shape (or a proxy the client is pointed at) remains work. 0043's
  "boots through our origin" was true for the document, never for the money
  calls; this is the correction.
* **The tap polls; it does not observe the round.** Two spins closer than the
  settle window can be conflated, and a spin that moves nothing produces no
  round. The server-side token makes a future server tap possible, but this
  decision keeps the existing per-spin reconcile.
* **The trial wallet is zero-value by construction.** No real money exists in
  this project; the PG session is a publisher demo session.
* **The tap's cross-origin fallback is gone.** An unsteered launch never
  showed the server `dt.tk`, so `/api/pg/wallet` returns `null` and the tap
  stays quiet rather than inventing a balance. That is deliberate.

## Alternatives rejected

* **Playwright / a bundled Chromium.** One more large dependency to reproduce
  what the installed browser already does; the CDP surface used here is small
  and stable.
* **Reading the spin answer.** PG's `game-api` is encrypted end to end; there
  is no payout to read. The wallet delta is the only authority.
* **Making the page talk to the publisher for the tap.** That is exactly the
  call the CORS policy blocks outside `*.pg-demo.com`; it also hands the
  player's browser a publisher credential it does not need.
* **Serving under `demo.pg-demo.com` and steering `ao` there.** The client
  rewrites `ao` to `api.pg-demo.com`, so the money calls leave our origin
  again. The document host has to match the rewritten name.
