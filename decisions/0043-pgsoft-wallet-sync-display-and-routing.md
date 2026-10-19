# 0043 — PG Soft wallet sync: display the player's saldo, route money to the api hosts

Status: built. PG stays `wallet_isolated`: spins are binary and still the
publisher's. What changed is everything around the spin.

> **Correction (0064, 2026-10-19).** "Routing to the api hosts" is true for
> calls the browser makes *through our path*. It does not make the money calls
> same-origin: PG's client calls `https://api.<label>.com` directly, and that
> host CORS-allows only `*.pg-demo.com` origins. A launch on our real origin
> therefore boots the document but loses the handshake — and production on
> `cadiback.onrender.com` hits the same wall. 0064 steers `ao` at the server
> for live checks and records the production work still needed.

## What was wrong

1. **Money rode the wrong host.** `pg_target` sent every sub-path to the
   minted game host (`m.<label>.com`). Measured 2026-10-15: that host
   answers 404 on `/web-api/...`, while the api host routes it (a bad
   token gets a 500 from the server, which is the credential refused, not
   the route missing). Every money call the client made through us died
   at the wrong origin.
2. **PG money was unclassified.** `MONEY_PATHS` had no `pg_soft` entry,
   so a `GameWallet/Get` answer kept the publisher's validators, could
   be pinned by a 304, and was cached like an asset.
3. **The game showed the wrong saldo.** `rewrite_balance` only reads
   form-encoded `balance=` fields; PG's balance is JSON
   (`{"dt": {"tb"/"cb"/"pb", "ch": {...}}}`), so the window showed the
   publisher's 100000.00 demo credits next to our HUD with the real one.

## What was built

- `pg_proxy.MONEY_TAILS` (`/web-api/`, `/game-api/`) + `pg_target` routes
  those tails to `session.api_hosts[0]`, sticky: the publisher's access
  token is session-scoped, so spreading one session across both api hosts
  would split it. Document and signed assets stay on the game host.
  `/healthcheck` stays on the game host too — it answers 200 there.
- `MONEY_PATHS["pg_soft"]`: the measured handshake paths, so money
  answers are no-store with withheld validators.
- `pg_proxy.rewrite_wallet`: `cb`/`tb`/`ch.cb` become the player's saldo
  in the publisher's own shape (floats stay floats, ints stay ints);
  `pb` follows so no phantom last-round delta appears; `tbb`/`tfgb`
  untouched (unknown semantics); non-JSON (the binary `GameInfo/Get`)
  passes through byte-for-byte. Counted as `balanced` in `/api/health`.
- Wired in both serve paths (`_serve_game`, `_serve_publisher_root`).

## What is still open

Settlement. The spin shape is binary and unobserved; a tap that
re-encodes it needs the real-browser capture from 0040 §7. Absolute
publisher URLs baked into the client bundle (if any) also bypass the
proxy — confirming that needs the same capture.

## Live smoke 2026-10-15 (through our own proxy, trial sessions)

- `POST /g/pg:fortune-tiger/pg/<sid>/web-api/auth/session/v2/verifySession`
  routes to the api host and returns a live `tk` + `geu` slug — the
  routing fix works against the real publisher.
- The following `GameWallet/Get` with that `tk` answers
  `err 3005 "Wallet not found"`. No cookies are involved (the verify
  answer sets none); the wallet most likely comes into existence only
  after the `GameInfo/Get` init in the measured sequence, which is
  binary and cannot be replayed by hand. Same capture as above settles it.
- `rewrite_wallet` itself is covered by unit tests over the captured
  answer shape; it activates the moment a real `dt.cb/tb` flows through.

## RESOLVED 2026-10-15 — boot works through our origin

The stall is gone. Three changes, all measured, no bundle RE needed:

1. **Full launcher query.** The launcher redirect carries
   `ot/l/btt/ao/or/__hv/__sv`; we sent only `ot/l/btt` (+ our token).
   `__hv`/`__sv` are the mint blob's own `hv`/`us` fields, forwarded
   verbatim (`pg_proxy.parse_triples` now reads the whole msgpack
   answer). `ao`/`or` are COMPUTED by name-mangling the api/static
   domains — algorithm recovered off the mint page itself
   (`pg_proxy.mangle`, verified byte-for-byte against a live launcher
   redirect: `mangle("api.f26xzzc7c.com", 18) == "18sha=x26prru7u=uge"`).
   With these the client fetches signed assets and attempts verify.
2. **Gi-rooted launches.** The client builds per-game asset URLs off
   its own path (`<static>/<gi>/<file>`), so launches are served from
   `/<gi>/` with the session in `?pg=` + cookie
   (`game_proxy.game_for_gi`, dispatcher branches, `pg_session`
   cookie). The old `/g/<id>/pg/<sid>/` path still routes.
3. **Money stays direct.** The client builds money URLs at runtime by
   unmangling `ao` (no literals to rewrite, and `ao` demonstrably
   selects the money host: naming us produced zero api calls, naming
   the api host produced verify attempts). Cross-site POSTs already
   work publisher-side (proven by direct runs); same-origin rewrite
   attempts were removed as dead code. Settlement therefore lives
   entirely in the bridge theater tap (0044).

## Full-handshake capture 2026-10-15 (`probes/pg-handshake-2026-10-15.json`)

Headless Chrome + ordinary UA, direct launcher run, 323 requests. What
it settled:

- The real wallet shape validates `rewrite_wallet`'s keys exactly:
  `dt.{cc,tb,pb,cb,tbb,tfgb,rfgc,inbe,infge,iebe,iefge,ch:{k,cid,cb},
  p,ocr,bwc,fgwc}`. No key was guessed.
- `GameInfo/Get`'s request is small form lines, its answer a
  compressed/encrypted blob (ASCII fragments inside, not plain
  protobuf) — decoding the spin needs this blob's format, not another
  guess at the URL.
- The client used the **rolling** static host and `?sign=` URLs for
  every asset; the unsigned `/shared/…` request our proxied run made
  exists nowhere in the direct run — under our origin the client's
  asset-base resolution falls back to a path the publisher never
  serves. Diagnosing that needs the bundle's base logic, not more taps.
- 13 taps (synthetic, trusted touch and mouse via CDP) never dismissed
  the canvas INICIAR splash, so **no spin was captured**. The one thing
  that unblocks settlement is still a real browser with a human pressing
  start once — this machine has no display and the engine ignored every
  synthesized press tried (untrusted events, trusted CDP mouse, trusted
  CDP touch, with and without mobile/touch emulation).

## Redirect discovery (the actual boot mechanism)

The launcher redirect carries more than `ot/l/btt` (read off a live
redirect with CDP):

    ?ot=…&l=pt&btt=2&ao=…&or=…&__hv=<blob hv verbatim>&__sv=<blob us verbatim>

- `__hv`/`__sv` are the mint blob's own `hv`/`us` fields, forwarded
  verbatim (`demo/pg_proxy.parse_triples` reads the whole msgpack
  answer now, not just the URL runs). The client signs its asset URLs
  from them.
- `ao`/`or` are launcher-computed (derivation unknown); the game boots
  past assets without them so far as measured, and they are NOT passed
  (nothing we have generates them — if a later call demands them, this
  is the thread to pull).
- Per-triple weights ride the blob too (`u` game URL 15/70/15,
  `ad` api hosts 80/20): the launcher picks weighted-random, which is
  why direct runs land on different triples. Our stable preference
  stays (allowlist stability), now with that triple's own `hv`/`us`.
- Our launch URL preserves the full minted query for the same reason:
  the client boots off `location.search`, and a launch carrying only
  our token left it session-less (that alone did not unstall it, but
  it is still required).
