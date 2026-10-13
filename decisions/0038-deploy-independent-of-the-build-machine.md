# 0038 — the deploy stopped depending on the build machine

Date: 2026-10-13. Status: **prepared and verified; awaiting one credential**
(the repository has no remote and Render has no account on this machine).

## The problem

The image copied `web/out` in from the build machine. So a deploy was not the
repository — it was "whatever box last ran `npm run build`, plus the tree",
and the export had to be rebuilt and committed by hand every time a
front-end file changed. Nothing about it said so: `Dockerfile` looked like a
normal, self-contained deploy.

The Cloudflare Worker path failed the same way one level up: it fronted a
backend running on a laptop, behind a quick tunnel whose hostname changes on
restart, under a temporary account that gets deleted (that one is confirmed
dead — `candibet.road-hydrant.workers.dev` no longer resolves).

## What changed

- **`Dockerfile` builds the storefront itself.** Stage 1 is `node:22-slim`
  doing `npm ci && npm run build`; stage 2 is `python:3.14-slim` copying
  `/build/out` in. A deploy is now *the repository plus the Dockerfile*.
- **`.dockerignore` inverted to match.** `web/app`, `web/lib`, `web/public`
  and the lockfile are back in the build context (the image needs them to
  build); the host's `node_modules`, `.next` and the live `demo/data` stay
  out.
- **A git repository, once**: 701 tracked files on `main`, `.gitignore`
  (no `node_modules`, no `web/out`, no `demo/data`, no wrangler state),
  `.gitattributes` normalizing LF so a Linux image never meets a CRLF in the
  shell scripts, first commit on top of the proxy work.
- **`render.yaml`**: `numInstances: 1` (the ledger is JSONL under one lock),
  and the free-plan data reality stated where the owner will read it.
- **`scripts/render_deploy.py`**: `--check` is a credential-free preflight
  (the tree a remote host needs, and nothing that would poison the build);
  the default mode creates-or-finds the service over the public API, deploys,
  and watches to `live`. The service settings live in one `SERVICE` dict so
  the script and the Blueprint cannot drift apart.

## How it was verified without Docker

1. **`npm ci && npm run build` from a clean tree** — the stage-1 command
   exactly as the image runs it: 21 packages, compiled, 3 static pages.
2. **The runtime file set, assembled by hand** — only what stage 2 copies
   (`frame/`, `demo/`, `probes/` minus caches, `web/out`), then
   `python -m demo.server` from that directory alone: `/api/health` ok,
   `/` 200, `/api/catalog` 10 in-house + 182 publisher rows, and
   `/g/pp:gates-of-olympus/` 200 straight from a live publisher through the
   proxy. No source file, no docs, no `scripts/` — so the image is proven
   sufficient, not merely plausible.
3. **A fresh `git clone`** — 701 files, with `web/out`, `demo/data` and
   `node_modules` absent: what Render would receive, checked before pushing.
4. **`python scripts/render_deploy.py --check`** — 0 problems.

Not verified: the Render build itself (no docker, no account). The two things
a remote build could still hit are the two this repo controls — the image
file set (verified above) and `npm ci` against the committed lockfile
(verified above) — not the hosting account.

## The one credential

Render needs a repository to build from, and this machine has neither a remote
nor a `RENDER_API_KEY`. Either one unlocks the last step:

- **Dashboard (no code changes):** push to a GitHub repo, then Render → New →
  Blueprint → Apply.
- **API (what I would run):** `RENDER_API_KEY` + `RENDER_REPO` in the
  environment, then `python scripts/render_deploy.py`.

## Free-plan caveat, stated plainly

Render's free web services have no persistent disk, so `OPERATOR_DATA_DIR`
(`/data`) is lost on redeploy **and on spin-down** (idle free services are
recycled after ~15 minutes). For a hobby simulation that is usually fine;
when it is not, uncommenting the `disk:` block in `render.yaml` on a paid
instance keeps the ledger, profiles and rounds across everything.