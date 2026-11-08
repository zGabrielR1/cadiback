# Handover — release 0106 (frontend-only Vercel publication)

Date: 2026-10-28
Status: **prepared and locally verified; not deployed.**

Continue from here next session. This file is the source of truth for the
remaining work; the earlier decision records 0102–0105 explain the code changes.

## Objective

Publish the frontend-only release **0106** to the existing Vercel project
`cadiback-web`. No backend code or environment change is part of this release.
Preserve the existing production `BACKEND_URL` and all other project settings.

- Target: <https://cadiback-web.vercel.app>
- Vercel project: `cadiback-web`
  - projectId `prj_6Jh0xUYaxyynpAgwymNuHnQd09ac`
  - orgId `team_B0hbPGEjWhgToE57kPE4C5zG`
- Base commit: `d69718ba5b76ebf2a7066eac25d773def16d59e8`
- Release snapshot: `/tmp/operator-release-0106`
  - `manifest.json` records SHA-256 for 397 frontend source/config files
  - `DEPLOYMENT.md` describes the publication command and post-deploy checks
  - `verification/` holds the prior session's logs

The snapshot is `/tmp` state and may be gone next session. If missing, rebuild it
from the repo: base commit `d69718b` plus the 11 overlaid working-tree files:

```
web/app/components/CasinoHome.jsx
web/app/components/CasinoSports.jsx
web/lib/localCache.js
web/lib/localCache.test.mjs
web/lib/sports.mjs
web/lib/sports.test.mjs
web/lib/sports-slip.test.mjs
web/lib/sports-feed.mjs
web/lib/sports-feed.test.mjs
web/lib/useSportsFeed.js
web/lib/useSportsFeed.test.mjs
```

The repo working tree at `ppp/projects/operator` currently contains these
changes. Do **not** commit the unrelated pre-existing tooling deletions,
`.impeccable/`, `web/out`, feed-cache edits, or other local noise.

## Gates completed this session (2026-10-28)

Run from `/home/pwdmcl/data/PPP/ppp/projects/operator`:

| Gate | Command | Result |
| --- | --- | --- |
| Backend | `UV_PY=/home/pwdmcl/.cache/uv/archive-v0/7JRctxnJXeuaNP7w/bin/python; $UV_PY -m unittest demo.test_demo` | **426 tests, OK** (the old 27 HTTP socket `PermissionError`s are gone in this environment) |
| Core | `$UV_PY -m frame.selftest` | **50 tests, OK** |
| Structure | `$UV_PY scripts/verify.py` | **93 files, 104 Python sources, 0 problems** |
| Frontend deps | `cd web && npm ci` | 22 packages installed |
| Static build | `cd web && npm run build` | **success**, export written to `web/out` |
| Component renders | `node scripts/check_market_render.cjs` | **73 renders PASS** |
| Node regressions (run subset) | `node --test web/lib/{localCache,sports,sports-slip,sports-feed,useSportsFeed}.test.mjs` | 7+8+6+4+4 = **29 pass, 0 fail** |
| Vercel auth | `cd /tmp/operator-release-0106/web && npx --yes vercel whoami` | **`henriquealveslohrayne-5245`** |

Notes:

- `web/node_modules` and `web/out` are pruned between sessions. Restore with
  `cd web && npm ci`; rebuild with `npm run build`.
- The snapshot's `web/node_modules` is a symlink to the repo's
  `web/node_modules`. A Turbopack build **inside the snapshot** fails with
  `Symlink [project]/node_modules ... points out of the filesystem root`.
  Build in the repo's `web/` instead; Vercel ignores `node_modules` via
  `web/.vercelignore`, so this does not affect deployment.
- `npx --yes vercel whoami` works in this OpenCode environment. The Codex
  sandbox escalation failures quoted in the prior transcript do not apply here.

## Remaining work

### 1. Browser / viewport QA (not done)

The previous Firefox 159 headless attempt segfaulted; a Playwright Chromium
install was started at `/tmp/operator-qa` but interrupted. Suggested path:

```
cd /tmp/operator-qa   # if missing: mkdir -p /tmp/operator-qa && cd /tmp/operator-qa
npm init -y
npm i playwright@1.55.0
npx playwright install chromium
```

Then serve the real static export locally and exercise the changed states at
1440 / 768 / 390 / 320 px:

- Casino sports recommendations: initial loading, slow load, first-load error,
  later failure with retained prices/timestamp, retry, empty feed.
- Sports board/detail/builder: malformed refresh keeps the last good board,
  retry recovers, selection stays usable only when the feed is healthy.
- Recent games: malformed cache entries do not break the lobby.

`python -m demo.server` serves `web/out` on `127.0.0.1:8765` (see
`demo/server.py` header). Use the existing `scripts/check_market_render.cjs`
for static renders, but browser QA must exercise real hydration/effects.

### 2. Publish

```
cd /tmp/operator-release-0106/web
npx --yes vercel --prod --yes
```

Before publishing, re-check `manifest.json` (all 397 SHA-256 entries) and
confirm no credentials or `.env` files are in the snapshot. The command uses
the linked project and its existing production environment; do not add or
change environment variables.

### 3. Post-publication verification

Confirm and record:

- Vercel deployment state **READY** and the production alias
  `https://cadiback-web.vercel.app` points at it.
- Real read-only endpoints: root `/`, `/health`, `/api/sports`, casino catalog
  (200s, expected fixture/game counts).
- Protected player route still returns **401** for guests.
- Controlled guest/member recovery flows with no live financial, identity,
  account or bet writes.
- Browser/viewport checks above against the deployed URL.

### 4. Record and commit

After a successful publication, add a `decisions/0106-...md` record with the
deployment ID, alias, gate results and any limits, then update `CURRENTTASK`
and `PROGRESS.md`. Commit only the release files and the record. Push only if
the owner's existing upstream authorization still applies (see decision 0101);
do not push unrelated local changes.

## Reference

- `DEPLOYMENT.md` in the snapshot
- Decisions `0102`–`0105` for the code changes and their local evidence
- Decision `0101` for the previous Vercel publication and upstream snapshot
- Logs from the previous session: `/tmp/operator-release-0106/verification/`
