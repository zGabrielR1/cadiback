# Deploying candibet — the short version

The platform is one Python process plus a Next.js export it builds itself.
`demo/server.py` serves both, so there is **no reverse proxy and no tunnel** —
the whole platform is one container that runs anywhere Docker runs.

## Where this is today (2026-10-14)

**It is live: <https://cadiback.onrender.com>.** Storefront, API, catalog
(10 in-house + 182 publisher games) and the publisher proxy, all from one
container that Render built from this repository. Decision 0039.

The tree is also deploy-ready and verified: it is a git repository on `main`
with a Dockerfile that builds the storefront from `web/` inside the image, so
a deploy is *the repository plus the Dockerfile* and needs nothing from the
machine that last ran a build.

| Check | Result |
| --- | --- |
| `npm ci && npm run build`, clean tree | 21 packages, 3 static pages |
| runtime file set alone (no docs, no sources) | boots, health ok, store 200 |
| `/api/catalog` from that tree | 10 in-house + 182 publisher rows |
| `/g/pp:gates-of-olympus/` from that tree | 200 live, through the proxy |
| `python scripts/render_deploy.py --check` | 0 problems |
| **live service** | `/api/health`, `/api/catalog`, `/` and `/g/…` all 200 |

## Running it locally

```bash
cd web && npm ci && npm run build && cd ..   # node_modules is pruned on purpose
python -m demo.server                          # http://127.0.0.1:8765
```

## Before any deploy, run the gates

```bash
make deploy-prep      # npm ci + npm run build + verify.py, in that order
make selftest         # frame/wallet/ledger  45 checks
make demo-test        # the playable product 191 checks
make deploy-check     # is the tree deployable by a remote host?
```

`verify.py` fails on a `web/out` older than its sources, so a storefront
cannot silently ship yesterday's build.

On Windows without `make`, or without `python3` on PATH, run the commands
directly (`npm ci`, `npm run build`, `python scripts/verify.py`,
`python scripts/render_deploy.py --check`).

## Going live on Render

Render builds the image from the repository and runs it; there is nothing to
push and no artifact to upload. Two ways in — pick one.

### A. Dashboard (one click, no credentials in code)

1. Point Render at this repository (already done: `cadiback`).
2. Render → **New → Blueprint** → pick the repo → **Apply**.
3. `render.yaml` is the contract; Render reads the service name, plan, health
   check and env vars from it.

### B. API (fully scripted — what I run for you)

```bash
python scripts/render_deploy.py            # create-or-find, deploy, watch
python scripts/render_deploy.py --yes      # redeploy the current commit
python scripts/render_deploy.py --url-only # where is it
```

**The credentials are already found automatically** (decision 0039):

| What | Where it comes from |
| --- | --- |
| API key | `RENDER_API_KEY`, else `.env.render` in the repo root, else `~/.render_api_key` |
| Repository | `RENDER_REPO`, else `.env.render`, else `~/.render_repo`, else **the git remote `origin`** |

`.env.render` is gitignored and holds one line (the bare key), or
`RENDER_API_KEY=…` / `RENDER_REPO=…` pairs. Nothing to set up.

The script mirrors `render.yaml` in `SERVICE`, refuses to deploy a tree that
fails the preflight, and prints the live URL. **A failed build now prints what
the build said** — `build_failed` from the API carries no reason, and the
reason lives only in the log stream, so the driver reads it itself.

### Two things that will bite you again

- **A service created in the dashboard builds with Render's Python
  buildpack**, not your Dockerfile: it runs `pip install -r requirements.txt`
  and fails with `Could not open requirements file`. The API still *reports*
  `"runtime": "docker"`. The switch is the `env` field; `runtime` alone does
  not do it. `configure()` sends both.
- **`python:3.14-slim` ships an `operator` group**, so `useradd operator`
  fails with exit 9. The Dockerfile uses `groupadd -f` + `useradd -g` now.

Both are written up in [`decisions/0039`](../decisions/0039-deploy-live-on-render.md).

### What the deploy gives you

- **`https://cadiback.onrender.com`** — the service already existed under the
  repository's name, so that is the URL. A new service would get
  `candibet.onrender.com` unless the name is taken.
- The storefront from the edge of Render's own instance — no tunnel, nothing
  on your machine, nothing that expires.

### Free-plan reality

- **No persistent disk.** `OPERATOR_DATA_DIR=/data` lives in the container, so
  the ledger, player profiles and rounds are lost when the instance is
  redeployed **or spun down** — Render recycles idle free services after
  ~15 minutes. Uncomment the `disk:` block in `render.yaml` on a paid
  instance and the demo comes back exactly as it was.
- **Cold starts.** First request after a spin-down takes ~30s.
- `numInstances: 1` is deliberate: the ledger is JSONL under one lock.

For a hobby simulation that resets is usually fine. When it is not, the disk
block is a one-line uncomment plus a paid plan.

## After the deploy: four smoke checks

```bash
BASE=https://cadiback.onrender.com

curl -s $BASE/api/health              # {"status":"ok", ..., "proxy":{...}}
curl -s $BASE/api/catalog | head -c 200
curl -sI $BASE/                        # 200, the storefront
curl -sI $BASE/g/pp:gates-of-olympus/  # 200 from the publisher, via the proxy
```

The fourth one is the real test: it exercises `game_proxy.fetch` against a
live publisher from wherever you deployed.

In the browser: register → deposit R$100 → open **Crash Nitro** → spin. That
one always settles on the books.

Then open a publisher title, but read the lane before you trust it:

- **Hacksaw** and **Play'n GO** settle on our wallet — a spin must appear in
  `/api/history` and in the Painel with the stake and the win.
- **Pragmatic Play** is free play for now: the client boots and talks to the
  publisher, but the round does not reach the books (decision 0036, session
  completion is the open frontier). Do not read that as a deploy failure.
- **Spribe** settles through the theater bridge; **PG Soft** is trial only.

## If a game does not load

`/api/health` reports the proxy (`proxy.upstream`, `proxy.failures`,
`proxy.bytes`, `proxy.redirects`) — decision 0037. That answers "did the
request reach the publisher, and did we get an answer back" before you go
looking at the browser console:

- `upstream: 0` → nothing reached the publisher: the game was never launched,
  or the session cookies are gone (a fresh tab, a new browser).
- `failures` climbing → the publisher is refusing, or the instance has no
  outbound network.
- `upstream` healthy but the game still frozen → it is the client, not the
  proxy; that is the open PP frontier in `decisions/0036`.

## The other paths (kept, not recommended)

| | Render/any Docker host | Cloudflare Worker fronting a tunnel |
| --- | --- | --- |
| Files | `Dockerfile`, `render.yaml`, `fly.toml` | `deploy/` |
| Hostname | `candibet.<host>`, stable | `candibet.<hash>.workers.dev` |
| Dies when | you stop the container | the tunnel or the account dies |
| Storefront from | the instance's disk | Cloudflare's edge |

The Worker path exists and works (`deploy/README.md`, decision 0023). Its
quick-tunnel hostname changes on every `cloudflared` restart and a
`--temporary` Cloudflare account is deleted about an hour after it is created
unless claimed. It is retired: the Worker
`candibet.road-hydrant.workers.dev` no longer resolves and nothing needs it
now that Render holds the same tree. Details in
[`deploy-paas.md`](deploy-paas.md) (Fly/Koyeb/Railway) and
`deploy/README.md`.

## What each piece needs on the machine

| Tool | Needed for | If missing |
| --- | --- | --- |
| `python3` | everything (the image pins 3.14) | — |
| `node` + `npm` | building `web/out` locally | the image builds it itself |
| `docker` | testing the image locally | let the host do it |
| `wrangler` | the Worker path only | not needed on Render |
| `cloudflared` | the Worker path only | not needed on Render |

**`docker` is still not installed on this machine, and that is what let
`useradd` (0039) reach Render unfixed.** The image build cannot be verified
locally; it can only be verified by deploying. What is verified locally is
everything up to it: `npm ci && npm run build` from a clean clone, and the
runtime file set booting and serving. When a Dockerfile change is not
reproducible on Windows — a Linux-only user, group, permission or syscall —
deploy it and read the build log rather than trusting the review.

## Keeping the ledger

`OPERATOR_DATA_DIR` (default `demo/data`, `/data` in the image) holds the
ledger, player profiles, rounds and admin sessions. **Mount a volume there**
or the demo starts empty on every fresh instance. No database needed — this
is a single-user hobby deployment backed by JSON/JSONL.

## Which admin password?

`demo/auth.py` seeds **`admin` / `admin`** on first boot, salted-SHA256 stored.
The Painel is hidden behind `Ctrl+Shift+A`, and `/api/admin*` answers 401
without a session. Change it from the panel ("Minha senha") immediately —
`/api/auth/password` refuses weak passwords and revokes the other sessions.
