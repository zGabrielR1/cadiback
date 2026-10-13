# 0023 — deploy on Cloudflare Workers (cadibet)

Date: 2026-10-12. Status: done. Newest file wins on conflict.

## Objective

Put the platform on a real, public URL under the name **cadibet**, on
Cloudflare Workers, without a licensing/commercial track: a hobby deploy,
no real money, nothing to protect beyond a URL that will be needed later.

## Decision

One Worker (`deploy/`, `name: "cadibet"`) serves the static storefront and
proxies the dynamic surface to the Python backend:

```
browser ──▶ cadibet.<account>.workers.dev   (Cloudflare Worker)
                 │  static: env.ASSETS  (../web/out)
                 │  /api/*, /g/*, /rgs/* ─▶ BACKEND_ORIGIN
                 ▼
          python -m demo.server  (frame wallet, cashier, game proxy, RGS)
```

The backend is **not** ported to the Worker: it is a threaded `http.server`
app (sockets, filesystem, `Books`), which Workers cannot host. It stays a
process; the Worker fronts it. Durable hosting of that process is a later
step (Cloudflare Container — `container/Containerfile` exists — or any
always-on host); for now a `cloudflared` quick tunnel exposes it.

Consequential change in `demo/server.py`: the game proxy now derives its
public origin from `X-Forwarded-Proto`/`X-Forwarded-Host` (falling back to
`Host`), because behind a proxy the `Host` header is the internal backend
host and the rewritten game URLs would otherwise carry the wrong scheme and
host. New `Handler._our_origin()`; the two call sites use it.

## Name

`cadibet` was checked free in the Cloudflare namespaces on 2026-10-12:
`cadibet.pages.dev` and `cadibet.workers.dev` are NXDOMAIN (available);
`cadibet.com` is registered but serves no HTTP; `cadibet.com.br` / `.bet` /
`.io` are free. Chosen: the Worker name `cadibet` ⇒
`cadibet.<account>.workers.dev`.

## Verified

- `frame` 44/44, `demo` 131/131, `verify.py` 0 problems (after the
  `_our_origin` change).
- Live against `https://cadibet.luminous-schooner.workers.dev`:
  `/` 200 (storefront), `/api/catalog` 200 (40 publisher demos + 6 in-house),
  `/api/sports` 200; end-to-end player → deposit R$100 → `wallet/launch`
  (`can_play` true) → `wallet/status` → `spin` (R$5 debit, reels returned).
- Same-origin writes work through the proxy: the Worker strips
  `Origin`/`Referer` (the backend's same-origin gate compares against a host
  it cannot see behind a proxy), else every write is `403`.

## Open / caveats

- Temporary account, unclaimed, deletes ~60 min after creation — claim URL
  is printed by `wrangler deploy --temporary`. Claiming makes the URL
  permanent on the owner's account.
- The tunnel hostname changes on every `cloudflared` restart and the site
  needs the backend + tunnel both up; re-run `deploy.sh` with the new
  `BACKEND_ORIGIN`. A stable backend host (or Container) removes this.
