# Deploy on a Python host (candibet)

> Quick version and post-deploy checks: [`deploy-easy.md`](deploy-easy.md).

Hosts the storefront **and** the Python backend as one container on one port,
so there is no reverse proxy and no tunnel. Gives `https://candibet.<host>`
(`candibet.onrender.com`, `candibet.fly.dev`, `candibet.koyeb.app`, …).

This replaces the Cloudflare-Worker-fronts-a-tunnel setup in
`deploy/README.md` for the case the tunnel's expiring hostname is not wanted.
The `deploy/` Worker path still works and stays as the static-front option.

## Why one container works

`demo/server.py` already serves the built storefront itself: `static_file()`
serves `web/out` and every `/api/*` route is on the same process. So the
container is just the backend plus its three inputs:

```
frame/      the wallet/ledger core
demo/       the server (API + publisher proxy + RGS interposition)
probes/     the provider-demo catalog it reads at startup
web/out/    the Next.js export it serves as static files
```

The image (`Dockerfile`) copies exactly those and runs
`python3 -m demo.server`.

## What changed to make it hostable

Two env-driven bits in `demo/server.py` (local defaults unchanged):

- `HOST` / `PORT` — the server binds `0.0.0.0:$PORT` instead of the hardcoded
  `127.0.0.1:8765`, so the host's router can reach it. (`run()` in
  `__main__`.)
- `OPERATOR_DATA_DIR` — where the ledger, profiles, rounds and sessions live,
  so a mounted volume can persist them across deploys. Default stays
  `demo/data`.

## Deploy

Build the storefront first — the image serves `web/out`, it does not build it:

```bash
cd web && npm run build && cd ..
```

**Fly.io** (`fly.toml`, region `gru`):
```bash
fly launch --copy-config --no-deploy   # creates app + the candibet_data volume
fly deploy
```

**Render** (`render.yaml`):
```bash
# New → Blueprint → point Render at this repo; it reads render.yaml
```
Render injects `$PORT` itself. The free plan has no persistent disk, so the
ledger resets on each deploy — uncomment the `disk:` block on a paid instance
to keep it.

**Koyeb / Railway**: point them at the `Dockerfile`; set `HOST=0.0.0.0`,
leave `PORT` to the platform, and mount a volume at `/data`.

**Plain Docker** (any VPS):
```bash
docker build -t candibet .
docker run -d -p 8080:8080 -v candibet_data:/data --name candibet candibet
```

## State

`OPERATOR_DATA_DIR` (`/data` in the image) holds the double-entry ledger,
player profiles, rounds and admin sessions. Mount a volume there or the demo
resets on every deploy/restart. No external database is needed — the demo is
a single-user hobby deployment backed by JSON/JSONL files.

## Name

`candibet.<host>` is free on every one of these hosts (`candibet.onrender.com`,
`candibet.fly.dev`, `candibet.koyeb.app`). A custom domain (`candibet.bet`, or any
subdomain of it) attaches the same way as on Cloudflare, once the domain is
registered — see `deploy/README.md` for the name notes.
