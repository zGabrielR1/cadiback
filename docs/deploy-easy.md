# Deploying candibet — the short version

The platform is one Python process plus a built Next.js export. It is already
served by `demo/server.py` itself, so there is **no reverse proxy and no tunnel
required** — that is the whole point of the path below.

## TL;DR — local run (no deploy at all)

```bash
cd web && npm ci && npm run build && cd ..   # node_modules is pruned on purpose
python -m demo.server                          # http://127.0.0.1:8765
```

## TL;DR — one command to a public URL

```bash
cd web && npm ci && npm run build && cd ..
docker build -t candibet .
docker run -d -p 8080:8080 -v candibet_data:/data --name candibet candibet
```

Open `http://127.0.0.1:8080`. To put it on a real hostname, push that image to
any Python host that reads the `Dockerfile` — `fly launch --copy-config
--no-deploy && fly deploy` (Fly, region `gru`) or point Render at the repo and
let it read `render.yaml`. Result: `https://candibet.<host>`, no tunnel, no
expiring account. Full detail in [`deploy-paas.md`](deploy-paas.md).

## Before you deploy, run the gates

```bash
make deploy-prep      # npm ci + npm run build + verify.py, in that order
make selftest         # frame/wallet/ledger  45 checks
make demo-test        # the playable product 191 checks
```

A deploy carries whatever is in the tree. `verify.py` fails on a `web/out`
older than its sources, so the storefront cannot silently ship yesterday's
build.

On Windows without `make`, or if `python3` is not on PATH, run the three
commands directly (`npm ci`, `npm run build`, `python scripts/verify.py`).

## What each piece needs on the machine

| Tool | Needed for | If missing |
| --- | --- | --- |
| `python3` | everything (the image pins 3.14) | — |
| `node` + `npm` | building `web/out` | the image serves it, never builds it |
| `docker` | the container path | let the host do the build |
| `wrangler` | the Worker path | `npx --yes wrangler`; needs an account |
| `cloudflared` | the Worker path *only* | not needed on the container path |

State of this machine as of 2026-10-13: `node`, `npm` and `python3` are
present; **`docker`, `wrangler` and `cloudflared` are not**, and there are no
Cloudflare credentials anywhere (no `.wrangler` config, no
`CLOUDFLARE_API_TOKEN`). So the container path here means "give Render/Fly the
repo", not "docker run" — and the Worker path needs `wrangler login` first.

`deploy.sh` builds `web/out` itself, so on a machine where `web/node_modules`
is pruned (it is, between sessions — see `AGENTS.md`) run `npm ci` once first
or the deploy dies on `npm run build`.

## The two paths, and which to pick

| | Container (recommended) | Worker fronting a tunnel |
| --- | --- | --- |
| Files | `Dockerfile`, `fly.toml`, `render.yaml` | `deploy/` |
| Account needed | the host's | Cloudflare's |
| Hostname | `candibet.<host>`, stable | `candibet.<hash>.workers.dev` |
| Backend | same process | your machine + `cloudflared` |
| Dies when | you stop the container | the tunnel stops, or the account dies |
| Storefront from | the container's disk | Cloudflare's edge |

The Worker path exists and works (`deploy/README.md`, decision 0023); it is
the wrong default for a hobby project because it has two things that expire —
the quick-tunnel hostname changes on every `cloudflared` restart, and a
`--temporary` Cloudflare account is deleted about an hour after it is created
unless claimed. Both are gone as of this writing: the last deploy,
`candibet.road-hydrant.workers.dev`, no longer resolves.

## After the deploy: four smoke checks

```bash
BASE=http://127.0.0.1:8080            # or https://candibet.<host>

curl -s $BASE/api/health              # {"status":"ok", ..., "proxy":{...}}
curl -s $BASE/api/catalog | head -c 200
curl -sI $BASE/                        # 200, the storefront
curl -sI $BASE/g/pp:gates-of-olympus/  # 200 from the publisher, via the proxy
```

The fourth one is the real test: it exercises `game_proxy.fetch` against a
live publisher and proves the proxy path works from wherever you deployed.

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

`/api/health` now reports the proxy (`proxy.upstream`, `proxy.failures`,
`proxy.bytes`, `proxy.redirects`) — decision 0037. That answers "did the
request reach the publisher, and did we get an answer back" before you go
looking at the browser console:

- `upstream: 0` → nothing reached the publisher: the game was never launched,
  or the session cookies are gone (a fresh tab, a new browser).
- `failures` climbing → the publisher is refusing or the backend has no
  outbound network.
- `upstream` healthy but the game still frozen → it is the client, not the
  proxy; that is the open PP frontier in `decisions/0036`.

## Keeping the ledger

`OPERATOR_DATA_DIR` (default `demo/data`, `/data` in the image) holds the
ledger, player profiles, rounds and admin sessions. **Mount a volume there**
or the demo resets on every restart. No database needed — this is a
single-user hobby deployment backed by JSON/JSONL.

## Which admin password?

`demo/auth.py` seeds **`admin` / `admin`** on first boot, salted-SHA256 stored.
The Painel is hidden behind `Ctrl+Shift+A`, and `/api/admin*` answers 401
without a session. Change it from the panel ("Minha senha") immediately —
`/api/auth/password` refuses weak passwords and revokes the other sessions.
