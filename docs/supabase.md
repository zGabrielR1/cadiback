# Supabase Postgres + Vercel — runbook (decision 0049)

The operator's state moves from JSONL/JSON files to Supabase Postgres; the
storefront moves from the Python container's static serve to Vercel. The
Python backend and `frame/` stay — Postgres becomes their disk.

## Credentials

Gitignored **`.env.supabase`** at the repository root (same never-in-chat flow
as `.env.resend` / `.env.turnstile`):

| Variable | Secret? | Meaning |
|---|---|---|
| `SUPABASE_URL` | no | `https://<ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | barely — public-ish | unused by the backend; the storefront never talks to Supabase directly |
| `SUPABASE_SERVICE_ROLE_KEY` | **yes** | migrations / emergency SQL only; never ships to a client |
| `DATABASE_URL` | **yes** | SQLAlchemy URL for the backend: `postgresql+psycopg://postgres:<PASSWORD>@db.<ref>.supabase.co:5432/postgres` (URL-encode the password). If direct connections fail from the host, use the transaction pooler (`:6543`) instead — same shape |

`demo/db.py` reads this file with the real environment winning, exactly like
`mail_env`/`turnstile_env`. `DATABASE_URL` unset or non-`postgresql…` means
files stay the default — nothing reads Postgres until it is set.

## Backend env (wherever Python runs)

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | the only new one; everything else unchanged (`OPERATOR_DATA_DIR` becomes vestigial once all stores are ported) |
| `ASAAS_*`, `RESEND_API_KEY`, `MAIL_FROM`, `TURNSTILE_*` | unchanged, carried by `render_deploy.py` as today |

`requirements.txt` (`sqlalchemy`, `psycopg[binary]`) ends the stdlib-only
container — the Dockerfile gains a pip step at the cutover. The *foundry kit*
stays stdlib-only; only the operator outgrows that rule, the way wall-e
already did.

## Vercel env (dashboard > project > Settings > Environment Variables)

| Variable | Value |
|---|---|
| `BACKEND_URL` | the backend's public URL (`https://cadiback.onrender.com` or its successor). No trailing slash |
| (nothing else) | `VERCEL=1` is automatic and flips `next.config.js` to server output; `NEXT_OUTPUT=server` forces it anywhere |

No `vercel.json` needed — Next is auto-detected, rewrites live in
`next.config.js`. After the first deploy, register the production host
(`<project>.vercel.app`, stable):

1. Cloudflare dashboard > Turnstile > widget > Domains — add it.
2. `TURNSTILE_HOSTNAMES` gains it (deploy carries it; `render_deploy.py`).
3. The Asaas webhook stays on the backend — Vercel never sees provider traffic.

Preview deployments get their own hosts: they exercise everything *except*
bot-gated login/signup (exact-hostname Turnstile policy), or point at a
backend with `turnstile_login` off.

## Cutover checklist

1. `.env.supabase` filled; `select` the fourteen tables after applying
   `supabase/migrations/`.
2. Stores ported one at a time behind `DATABASE_URL`; `demo.test_demo` green
   throughout (SQLite) plus a staging-schema pass against Supabase.
3. Vercel deploy with `BACKEND_URL`; smoke `/api/health`, `/api/config`,
   login, a demo deposit, one game launch.
4. Backend `DATABASE_URL` set where Python runs; file paths retire.
5. Live-verify exactly as in 0045/0047/0048; record the result in the decision.
