# deploy — candibet on Cloudflare Workers

> **This is not the default path any more.** The single-container route
> (`Dockerfile` + `fly.toml` + `render.yaml`, no tunnel, no expiring account)
> is the one to reach for: see [`../docs/deploy-easy.md`](../docs/deploy-easy.md).
> Everything below is kept working and is here for when the CDN front is
> actually wanted.

Publishes the hobby platform at a real URL:

```
https://candibet.road-hydrant.workers.dev
```

One Cloudflare Worker (`name: "candibet"`) does two jobs:

1. **Serves the static storefront** — the Next.js export in `../web/out`
   (`env.ASSETS`, SPA fallback), from Cloudflare's edge.
2. **Proxies the dynamic surface** — `/api/*` (wallet, cashier, sports,
   admin), `/g/*` (publisher game proxy) and `/rgs/*` (RGS interposition) —
   to the Python operator backend named by `BACKEND_ORIGIN`.

The Python backend cannot run on a Worker (it is an `http.server` app: threads,
sockets, filesystem), so it stays a normal process and the Worker fronts it.

## Files

| File | Role |
|------|------|
| `wrangler.jsonc` | Worker config: name `candibet`, assets binding, `BACKEND_ORIGIN` var |
| `src/index.js` | The Worker: serve assets, else proxy the dynamic prefixes |
| `deploy.sh` | Build the export and deploy with the current backend origin |
| `backend.sh` | Start the Python backend + a public `cloudflared` tunnel |

## Deploy

```bash
# 1. backend in front of the internet (prints the https://….trycloudflare.com URL)
./backend.sh

# 2. point the Worker at it and publish
BACKEND_ORIGIN=https://<the-tunnel-host> ./deploy.sh
```

`deploy.sh` runs `npm run build` in `../web` and then `wrangler deploy`.
With no Cloudflare credentials present it uses `--temporary` (a throwaway,
claimable account — see below). With `CLOUDFLARE_API_TOKEN` set (or after
`wrangler login`) it deploys to your own account instead — drop the
`--temporary` flag in `deploy.sh` for that.

## The two things that expire

**These are the caveats, not bugs.** Both are by design for a hobby project:

1. **The temporary Cloudflare account** is deleted ~60 minutes after it is
   created *unless claimed*. Claiming is one click and makes the URL
   permanent on your own account:

   ```
   Claim URL: https://dash.cloudflare.com/claim-preview?claimToken=<token>
   ```

   The claim token is printed by `wrangler deploy --temporary` (see
   `~/.config/.wrangler/logs/` for the last run). Once claimed, deploy with
   your own `CLOUDFLARE_API_TOKEN` and the URL stops depending on a
   throwaway account.

2. **The backend tunnel** is a quick tunnel: the hostname changes every time
   `cloudflared` restarts, and the site only works while the backend process
   and the tunnel are both up on the machine running them. After a restart,
   re-run `./deploy.sh` with the new `BACKEND_ORIGIN`.

   Durable alternative: deploy the backend as a **Cloudflare Container**
   (`../container/Containerfile` already exists) or run it on any always-on
   host, then set `BACKEND_ORIGIN` to its stable hostname.

## Why `Origin` is dropped in the Worker

`demo/server.py` gates writes on a same-origin check (`Handler._same_origin`)
comparing the `Origin` header against its own `Host`. Behind a proxy those
never match, so every write would be refused with `403 cross-origin writes
refused`. The Worker is the trust boundary (browser → Worker → backend), so
it strips `Origin`/`Referer` and forwards `X-Forwarded-Host` /
`X-Forwarded-Proto`, which the backend uses for the public origin it bakes
into rewritten game URLs.

## Why a game's root-level request must reach the backend

A page-proxied game (Pragmatic Play, Spribe) spawns requests on **our own
origin** at root-level paths — its asset/config/server URLs and where it
navigates (`/gs2c/…`, `/apps/…`). The backend catches those in
`Demo._serve_publisher_root` (cookie-gated on `proxy_host`) and proxies them
to the publisher, which is why these games work locally.

The Worker used to forward only `/api/`, `/g/`, `/rgs/` to the backend, so
those root paths fell through to the assets layer — and, with
`not_found_handling: "single-page-application"`, the assets layer answered
them with `web/out/index.html`. The game frame then rendered the **whole
storefront**, and clicking the game inside it opened another frame: the
"loop mirror". The export has no client router, so the SPA fallback protected
nothing.

The fix (decision 0033): `not_found_handling` is now `"none"`, and
`src/index.js` routes a non-asset miss that **carries the proxy session
cookie** to the backend. Real assets and `/` still win, so the storefront is
untouched; a root miss without a session is a plain 404.

## Name checks

| Name | State |
|------|-------|
| `cadibet.pages.dev` | free (NXDOMAIN, checked 2026-10-12) |
| `cadibet.workers.dev` | free (NXDOMAIN, checked 2026-10-12) |
| `cadibet.com` | registered; no HTTP response (checked 2026-10-12) |
| `cadibet.com.br` / `.bet` / `.io` | free (NXDOMAIN, checked 2026-10-12) |
| `candibet.*` | checked 2026-10-12, see below |
| `candibet.pages.dev` | TAKEN (resolves) |
| `candibet.workers.dev` | free (NXDOMAIN) |
| `candibet.com` | TAKEN (resolves) |
| `candibet.com.br` / `.bet` / `.io` | no DNS answer (probably free) |

## Live right now (2026-10-12 ~22:50Z, temporary)

- Site: **https://candibet.road-hydrant.workers.dev** (temp account —
  claim within ~60 min or it is deleted; then it needs your credentials).
- Backend: the dev machine's `:8765` via quick tunnel
  `https://gba-simon-act-cardiff.trycloudflare.com`. Both processes must
  stay up; the tunnel hostname changes on restart (re-deploy with the new
  `BACKEND_ORIGIN`).
- Verified live: register → deposit R$100 → Crash Nitro 2.00x → R$105.00;
  catalog 9 in-house + 182 publisher rows.
- To keep it (your call): `wrangler login` (or set CLOUDFLARE_API_TOKEN),
  re-run `BACKEND_ORIGIN=<tunnel-url> ./deploy.sh`; for a stable home see
  `docs/deploy-paas.md` (single `candibet` container, no tunnel).
