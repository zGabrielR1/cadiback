# AGENTS — operator

High-fidelity 1:1 hobby betting platform and casino simulation for personal usage.
No real money moves; no commercial legal or regulatory obligations.

## Structure

| File / Folder | Role |
|---------------|------|
| `AGENTS.md` | This instruction map |
| `ARCHITECTURE.md` | System map: layout, lifecycle, seams |
| `PROGRESS.md` | State tracker — completed capabilities & hobby milestones |
| `CURRENTTASK` | Active objective tracker |
| `Makefile`, `scripts/verify.py` | Executable verification: tests, structure, links |
| `decisions/` | Decision log, one file per decision |
| `frame/` | Core double-entry wallet, ledger, and rules (45 checks) |
| `demo/` | Playable server: Pix simulation, in-house slots, risk monitor (191 checks) |
| `web/` | Next.js 16 + React 19 storefront with embedded official games |
| `Dockerfile`, `render.yaml` | The deploy: one container, built and run by the host |
| `docs/gap-assessment.md` | Scoreboard: 1:1 simulation fidelity |
| `docs/deploy-easy.md` | Ship it: gates, the two paths, smoke checks, triage |
| `docs/audit-2026-10-01.md` | Audit findings & ledger integrity fixes |
| `probes/` | Provider demo catalog (182 official games) & live sports fixtures |
| `archive/` | Retired deploy paths and old specs — code only, never deployed |

## Workflow

1. Read `CURRENTTASK`, `AGENTS.md`, and `PROGRESS.md`.
2. Consult `ARCHITECTURE.md` and `decisions/`.
3. Keep code clean, functional, and aligned with 1:1 platform replication.
4. Run `python scripts/verify.py`, `python -m frame.selftest`, and `python -m unittest demo.test_demo`.
5. Rebuild the frontend (`cd web; npm.cmd run build`) whenever modifying `web/app`.
   `web/node_modules` is deliberately pruned between sessions to keep
   backups small — restore it with `cd web; npm.cmd ci` before building.
