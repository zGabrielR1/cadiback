# 0037 — Publisher game proxy: leaked credentials, half a bundle, no cache

Date: 2026-10-13. Status: **done** — `demo` 191/191, `frame` 45/45,
`verify.py` 0 problems, live smoke against two publishers.

Scope: `demo/game_proxy.py` and the two proxy handlers in `demo/server.py`,
plus the two feed seams in `frame/verticals/sports/` that leak the same way.
No behaviour a game depended on changed: the launcher, the bridge, the money
paths and the redirect handling are as they were, verified live.

## Bugs found

1. **The player's wallet token went to the publisher.**
   `Handler._serve_game` forwarded `parsed.query` verbatim, so the
   `wallet_token` (or the `token` of a direct launch) that rides along to keep
   the document bound to the player also landed in the publisher's access log —
   and with it the one credential that can spend that player's saldo. Now
   `publisher_query` drops ours, except on a provider we interpose at the RGS,
   where the token *is* the game's plumbing (it reads it off its own URL and
   hands it back to `POST /api/wallet/round`).
2. **A publisher answer was truncated at 12 MB and served as if whole.**
   `resp.read(MAX_BODY)` returns what fits and stops. A Unity bundle past that
   size reached the client half-deserialized — precisely the "empty game root"
   class of death decision 0036 spent a session on, with nothing in the
   console pointing at the cut. The cap is now a refusal (502) rather than a
   silent truncation, and it is 32 MB.
3. **Every upstream error held its connection open.** An `HTTPError` *is* a
   response; reading it without closing it keeps the socket until the
   collector runs. The demo suite showed it as a `ResourceWarning` on every
   run (a publisher 503). Closed now in `game_proxy.fetch`, and in
   `espn_engine._http` / `superbet_engine._http`, which had the same shape on
   a feed polled every 30 s. The suite is clean under
   `python -W error::ResourceWarning`.
4. **`rebase` repaired exactly one spelling of `<base>`.** The regex matched
   `<base href="/">` and nothing else: a publisher writing `<base href='/'>`,
   `<base target=_top>` or an absolute href got no repair, and a single-page
   game with no base under a proxy path never initialises — it sits on its
   connection screen saying nothing. The tag is matched now, whatever it says.
5. **Client patches ran on non-script bodies.** `patch_unity_client` /
   `patch_spribe_client` were applied to any rewritable content type, so the
   same substitution could land inside markup the publisher wrote. Gated on
   the body being script (`CLIENT_PATCHERS`).
6. **`inject_bridge` could be closed out by its own config.** The launch
   symbol comes off a publisher URL and is written into a `<script>` element;
   JSON escapes quotes but not `<`. `_script_json` escapes it.
7. **The HUD threw when the document had no body yet.** The bridge is injected
   in `<head>`; `document.body.appendChild` on a null body would have taken
   the money path down instead of the toast. Rooted at `documentElement`.
8. **`HEAD` answered 501.** Any probe or cache revalidation for a proxied
   asset was told the resource does not exist. `do_HEAD` answers like the GET,
   and `_send` sends no body and no `Content-Length` for HEAD/204/304.
9. **A doubled charset.** `_send` appended `; charset=utf-8` to a publisher
   type that already declared one: `text/javascript; charset=utf-8; charset=utf-8`.
10. **A publisher edge error was cacheable for a week.** Live: `/favicon.ico`
    answers `450` with no policy of its own, and its 404s answer
    `max-age=604800`. Both were served with that policy. Anything at or above
    400 is now `no-store`.

## Improvements

- **The cache the proxy never had.** Every answer went out `no-cache` with no
  validators, so a reload re-downloaded the whole game through us. Now:
  - an untouched asset keeps the publisher's `Cache-Control`/`ETag`/
    `Last-Modified`, and the client's `If-None-Match` is forwarded so a
    reload costs a 304;
  - a body we may rewrite (document, money answer, script/config) is **not**
    validated in either direction: our bytes are not the bytes the validator
    describes, so the client's validator is withheld upstream and none is
    advertised downstream;
  - a publisher 304 on such a body is re-fetched unconditionally — an empty
    answer cannot be patched, and forwarding it would pin the client to bytes
    we never computed;
  - `Range` is forwarded and `Content-Range`/`Accept-Ranges` come back, so a
    media request that does come through us is not truncated by us.
- **`GET /api/health` reports the proxy**: upstream calls, failures, bytes and
  redirects. A game that does not load used to leave no trace on the server,
  and "was it us or the publisher" was the first question and the hardest to
  answer.
- **`target_url` is vetted by `checked_url`**, the one place a scheme and host
  are checked, so a joined URL cannot leave the publisher even if a future
  mapping changes how the join is built.

## Deliberately not changed

- **The Worker (`deploy/src/index.js`).** It is a live deploy surface and its
  routing was verified by hand in 0033; nothing here was wrong with it.
- **The bridge's `cfg.bet_url` fetch/XHR hooks** stay inert: no provider is
  mapped, and a half-implemented gate on a publisher's own envelope is worse
  than none. The socket tap (Play'n GO) and the PP boot repairs are the live
  paths.
- **Script bundles are still re-fetched whole** on reload. That is the honest
  cost of patching them: an unpatched body would revalidate, but we cannot
  know it is unpatched before we have it. The win is on the binary assets and
  on the root-level requests the game client spawns through us.

## Verification

- `python -m unittest demo.test_demo` → 191/191 (was 171).
- `python -m frame.selftest` → 45/45 (was 44).
- `python -W error::ResourceWarning -m unittest demo.test_demo` → clean.
- `python scripts/verify.py` → 0 problems.
- Live, on `127.0.0.1:8765`: PP launcher 200 with one `charset`, session
  cookies, `no-cache`; `build.js` (3.1 MB) 200, publisher policy, no
  validator advertised; HEAD on the same asset 200 with headers and no body;
  a missing asset answered `no-store` where it used to be a week; Hacksaw
  interposed launch still carries its token into the publisher URL and the
  bridge config still lands in the document.