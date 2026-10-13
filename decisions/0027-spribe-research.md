# 0027 — Spribe: research and what it takes (Aviator)

Date: 2026-10-12. Status: **the client blocker is solved** — Aviator runs from
our origin; the money tap is the remaining step. Newest file wins on conflict.

## SOLVED — the client is hostname-coupled through domain mirroring

`console.log` showed nothing and there were no errors, so the stall was found
by giving the page a publisher-shaped hostname (`local.spribegaming.com` via a
resolver map): it connected immediately. The mechanism is in the client:

```js
const Dfe = ["adjarabet","spribegaming","spribe"];
mirrorHostname(t){
  if (!f_.isDomainMirroringEnabled || !this.secondLevel || !this.topLevel
      || Dfe.includes(this.secondLevel)) return t;
  const i = t.split(".");
  return t.replace(`.${i[i.length-2]}.${i[i.length-1]}`,
                   `.${this.secondLevel}.${this.topLevel}`)
}
```

Spribe **mirrors the vendor's hostnames onto the site's own second-level
domain** — `app-demo2.spribegaming.com` becomes `app-demo2.<our-domain>` —
because a real operator aliases those hosts under their own domain. A personal
deploy has no such aliases, so the client dials a host that does not exist and
sits on "Ligação…" forever. On a `*.spribegaming.com` host the mirror list
exempts it, which is the only way it ever worked.

**Fix (small, targeted):** switch mirroring off in the served bundle —
`mirrorHostname(t){return t; …}` (`game_proxy.patch_spribe_client`).
Verified on plain `http://127.0.0.1:8765`: the client connects to the real
`wss://app-demo2.spribegaming.com/BlueBox/websocket`, completes the SFS
handshake, and renders the full live game (canvas, bet feed, multipliers).

### How it was pinned down

- **The app works.** Loading the publisher's own page with only the config
  stubbed (their CDN 403s browsers — point 3 below) connects and renders. That
  working reference is what cracked it.
- Ruled out: the config bytes (identical), our wallet bridge (fails without
  it), HTTPS/secure context (fails over TLS too), missing requests (sets
  match), console errors (none), user gesture, `postMessage` handshake,
  `<base href>` (fixed anyway — see below), SFS origin validation (101 from
  any origin).

## Remaining: the money tap

The SFS stream is SFS2X binary with typed keys — captured live:
`betId`, `winAmount`, `multiplier`, `cashouts`, `openBetsCount`,
`game_state`, `currentBetsInfoHandler`. Reading a round's stake/win from those
frames and reporting it to `POST /api/wallet/round` (decision 0026) is the
last step, plus holding the spin back at R$0. The socket is plain
`wss://app-demo2.spribegaming.com/BlueBox/websocket` and needs no proxy — the
browser reaches it directly, so a client-side tap (like Play'n GO) applies.

## What landed earlier in the session (all still needed)

1. **The launcher redirects, and the session lives in the URL.**
   `demo.spribe.io/launch/<game>` → 302 →
   `<game>-demo.spribegaming.com/?…&user=&token=`. Built: redirects are handed
   to the browser, rewritten onto our origin (`REDIRECT_PROVIDERS`), carrying
   our wallet token as `wallet_token`.
2. **The SPA ships `<base href="/">`.** Built: `rebase()` points it at the
   document's own path.
3. **The config host is broken for browsers.** `app-config.spribegaming.com`
   **403s browser-like requests and sends no CORS**, so the publisher's own
   demo cannot start in a browser today. Built: `SERVICE_HOSTS` routes it
   through us.
4. **The socket is reachable and not origin-validated** (101 from any origin).

## What landed this session (code)

- `game_proxy`: publisher domains allowed by **suffix** (lookalikes refused);
  `SERVICE_HOSTS` rewrite; `fetch(follow=False)`; `REDIRECT_PROVIDERS`;
  `rebase()`; **`patch_spribe_client`**.
- `server`: redirect passthrough (`_pass_redirect`) with the session and
  `wallet_token` preserved; document-host cookie; bridge injected into the
  redirected document; 500s log a traceback.
- Tests: `demo` 139/139 (`GameProxyTest` +5), `frame` 44/44, `verify.py` 0.


## What Spribe actually is

1. **The launcher redirects, and the session lives in the URL.**
   `demo.spribe.io/launch/<game>` → 302 →
   `<game>-demo.spribegaming.com/?currency=…&operator=demo&jurisdiction=CW&lang=pt&user=<id>&token=<token>`.
   The Angular app reads `user`/`token` from `location`, so a proxy that
   follows the redirect server-side strips the session. **Built**: redirects
   are handed to the browser, rewritten onto our origin
   (`game_proxy.REDIRECT_PROVIDERS`), with our wallet token carried alongside
   as `wallet_token` so the document stays bound to the player.

2. **The SPA ships `<base href="/">`.** Every relative URL resolves against
   the origin root, so the catch-all must fetch from the document's own host —
   `<game>-demo.spribegaming.com`, not the catalog host. **Built**: the
   document host is bound into the proxy cookies.

3. **The config host is broken for browsers.** The app fetches
   `app-config.spribegaming.com/<game>/demo?v=<build>` (a constant,
   `appConfigPath`, in `main.js`). That host **answers 403 to browser-like
   requests and sends no `Access-Control-Allow-Origin`**, so the publisher's
   own free-play demo cannot start in a browser today — the direct demo shows
   *"Retry limit of client config exceeded!"*. Our server (plain UA) gets
   `200` with `ACAO: *`. **Built**: `game_proxy.SERVICE_HOSTS` rewrites that
   URL through us; the config now loads.

4. **The money runs over SmartFoxServer.** The config names the game server:
   `{"ws":{"host":"app-demo.spribegaming.com","port":443,"zone":"aviator_core","useSSL":true}}`,
   and the client connects `wss://<host>:443/BlueBox/websocket` (SFS *BlueBox*
   tunnel — **not** `/WebSocket`).

5. **The socket is reachable and not origin-validated.** A raw handshake to
   `wss://app-demo.spribegaming.com:443/BlueBox/websocket` answers **101
   Switching Protocols** for both `Origin: https://aviator-demo.spribegaming.com`
   and `Origin: http://127.0.0.1:8765`. So a **server-side socket proxy is
   viable** — our server opens it with the publisher's Origin.

## Where it stands

With points 1–3 built, Aviator loads **fully through our origin**: every
asset, the config, and the wallet bridge (our HUD shows our saldo). It then
sits at **"Ligação…"** (connecting) and **no socket is opened at all**.
Point 5 says the endpoint is fine, so the gap is client-side, before connect.

## Actionables, in order

1. **Find why the client never opens the socket.** It is reachable, so the
   app is gating. Cheap hypotheses to test in order:
   - **Secure context**: the app may refuse to connect from `http://`. Serve
      the same page over `https` (the PaaS/tunnel deploy does this) and watch
      for the WS.
   - **Embed gating**: the launcher may require `embedMode`/`isExternalGame`
      or a click in a specific control before connecting.
   - **A handshake call first**: SFS BlueBox is often entered after an HTTP
      "bluebox" probe; capture the app's own `fetch`/XHR during "Ligação…".
2. **Then write the server-side socket proxy.** We already know the upstream
   accepts any Origin, so this is our process opening the socket (with the
   publisher's Origin) and relaying frames — no browser origin problem. The
   remaining unknown is the **SFS wire format** (BlueBox frames are
   base64-wrapped SFS messages): decode the bet / win / balance opcodes the
   way PGO's line protocol was decoded.
3. **Then settle rounds** through the existing `POST /api/wallet/round`
   (decision 0026) — same shape as Play'n GO: read the stake, take the round's
   net, gate the spin at R$0.

## What landed this session (code)

- `game_proxy`: publisher domains allowed by **suffix** (a game is served from
  its own subdomain), lookalikes still refused; `SERVICE_HOSTS` rewrite;
  `fetch(follow=False)`; `REDIRECT_PROVIDERS`.
- `server`: redirect passthrough (`_pass_redirect`) with the session and
  `wallet_token` preserved; document-host cookie; bridge injected into the
  redirected document; 500s now log a traceback server-side.
- Tests: `demo` 138/138 (`GameProxyTest` +4), `frame` 44/44, `verify.py` 0.

## Honest read

Points 1–4 are the bulk of a Spribe integration and are done. What remains is
one client-side gate (actionable 1) and the SFS wire decode (actionable 2) —
real work, but the shape is now known end to end, and unlike Play'n GO it
does not need a vendor account.
