# 0033 — Deploy Worker: game root requests no longer serve the storefront

Date: 2026-10-12. Status: **fixed** — `frame` 44/44, `demo` 161/161,
`verify.py` 0 problems, Worker routing unit-checked.

## 1. Symptom

On the deployed site, launching a page-proxied game (Pragmatic Play, Spribe)
made the game frame render **another copy of the whole storefront**: the
player clicked the game again inside it, opening another frame, and so on —
a "loop mirror" of the site. Locally (raw backend) the same games launched
fine.

## 2. Root cause — the Worker's routing, not the game proxy

The game proxy itself handles these providers correctly. A page-proxied
client (PP's Unity client derives its URLs from `location.origin` /
`ServerOptions.serverUrl`; Spribe's launcher) spawns requests at our origin
on **root-level paths** — its asset/config/server paths (`/gs2c/…`,
`/apps/…`) and its navigation targets. On the backend those are picked up
by `Demo._serve_publisher_root` (cookie-gated on `proxy_host`/`proxy_game`)
and proxied to the publisher — which is why the games work locally.

Behind the Cloudflare Worker (`deploy/src/index.js`) only `/api/`, `/g/` and
`/rgs/` are forwarded to the backend (`isDynamic`). A root-level game request
is *not* in that set, so it fell through to `env.ASSETS.fetch`, and
`wrangler.jsonc` had `"not_found_handling": "single-page-application"` — which
answers **any** unmatched path with `web/out/index.html`. Served as a
document, that is the entire storefront, so the game frame became the site.

The export is a single page with **no client router** (`useRouter` /
`usePathname` appear nowhere under `web/app`), so the SPA fallback protected
nothing; it only ever masked misses with the storefront.

PP and Spribe are exactly the two providers that derive root-level URLs from
our origin; the others (Hacksaw, Play'n GO, PG Soft trial) keep their assets
on the publisher CDN, which is why the loop looked specific to those two.

## 3. Fix

- `deploy/wrangler.jsonc`: `not_found_handling` → `"none"`. A miss is a real
  404 again, never the storefront.
- `deploy/src/index.js`: when a non-dynamic request is **not** a static asset
  and **carries the publisher-proxy session cookie**, forward it to the
  backend, where `_serve_publisher_root` proxies it to the publisher (or
  404s). Real assets and `/` still win, so the storefront is protected.
- `demo/server.py`: `/api/wallet/launch` built the interposed launch URL from
  `"http://" + Host` (hardcoded scheme, internal host). It now uses
  `_our_origin()`, so behind the Worker the URL is the public
  `https://<site>/g/<game>/…` the browser can actually load. Only Hacksaw is
  interposed today; the bug was latent for the deploy.

## 4. Verification

`deploy/src/index.js` was exercised headless with a stubbed assets binding and
backend `fetch`: `/api`, `/g`, `/rgs` proxy; `/` is served as the storefront
and not proxied; a root-level request **with** the session cookie proxies to
the backend (with `X-Forwarded-Host`/`Proto` set and `Origin` stripped); a
root miss **without** the session is a 404, not the site.
