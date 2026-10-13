# Deploying candibet — the short version

The platform is one Python process plus a Next.js export it builds itself.
`demo/server.py` serves both, so there is **no reverse proxy and no tunnel** —
the whole platform is one container that runs anywhere Docker runs.

## Where this is today (2026-10-13)

The tree is **deploy-ready and verified**: it is a git repository on `main`
with a Dockerfile that builds the storefront from `web/` inside the image, so
a deploy is *the repository plus the Dockerfile* and needs nothing from the
machine that last ran a build.

Checked, in this order:

| Check | Result |
| --- | --- |
| `npm ci && npm run build`, clean tree | 21 packages, 3 static pages |
| runtime file set alone (no docs, no sources) | boots, health ok, store 200 |
| `/api/catalog` from that tree | 10 in-house + 182 publisher rows |
| `/g/pp:gates-of-olympus/` from that tree | 200 live, through the proxy |
| a fresh `git clone` | 701 files, no `web/out`, no `demo/data` |
| `python scripts/render_deploy.py --check` | 0 problems |

What is **not** done: the repository has no remote, and there is no Render
account configured on this machine. Both need one credential from you — see
[Going live on Render](#going-live-on-render).

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

1. Push this repository to a **public** GitHub repo (or connect a private one
   in Render's dashboard).
2. Render → **New → Blueprint** → pick the repo → **Apply**.
3. `render.yaml` is the contract; Render reads the service name, plan, health
   check and env vars from it.

### B. API (fully scripted — what I run for you)

```bash
export RENDER_API_KEY=rnd_...        # Render dashboard > Account > API Keys
export RENDER_REPO=https://github.com/<you>/<repo>
python scripts/render_deploy.py      # create-or-find, deploy, watch to live
```

The script mirrors `render.yaml` in `SERVICE` (one place, so the two cannot
drift), refuses to deploy a tree that fails the preflight, and prints the
live URL. Re-running it after a push is the whole update cycle; `--yes`
redeploys an existing service.

### What the deploy gives you

- `https://candibet.onrender.com` — Render assigns the name; if it is taken
  the service still builds, under `candibet-xxxx`.
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
BASE=https://candibet.onrender.com

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
unless claimed. Both are gone as of this writing: the last deploy,
`candibet.road-hydrant.workers.dev`, no longer resolves. Details in
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

State of this machine as of 2026-10-13: `git`, `node`, `npm` and `python3`
present; **`docker`, `wrangler`, `cloudflared` and `gh` are not**, and there
are no Render or GitHub credentials anywhere. That is why the deploy is a
repository plus a Render account, and why nothing above needed this machine
at the far end.

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
