# 0049 — Backend state to Supabase Postgres, storefront to Vercel

Date: 2026-10-15
Status: accepted

## Context

The operator is one stdlib-only container on Render: `demo/server.py` serves the
API *and* the static Next.js export, and all state lives in JSONL/JSON files
under `OPERATOR_DATA_DIR`. That shape has two ceilings we have now hit:

1. **No durable state.** Render free has no disk; every redeploy or ~15min idle
   spin-down wipes players, ledger, sessions and settings.
2. **No separate frontend.** The storefront cannot move to Vercel while the only
   thing serving it is the Python process — and the backend's `_same_origin`
   gate refuses cross-origin POSTs, so a split origin needs deliberate work.

The decision: **keep the Python backend and `frame/`; move its state to Supabase
Postgres; move the storefront to Vercel.** What was asked for, in that order.

## Decision

### 1. Python stays, Postgres becomes its disk (not a BaaS rewrite)

Supabase cannot run `demo/server.py` — it is Postgres + Auth + edge functions,
not a Python host. A BaaS rewrite (Auth + PostgREST + Edge Functions, retiring
`demo/` and `frame/`) would discard the 269-test executable spec that is the
only proof the money logic is right. Rejected.

So the backend keeps running on Render/Fly and talks to Supabase Postgres. The
persistence seam reuses wall-e's exact shape (`src/wall_e/db.py`): SQLAlchemy,
one `DATABASE_URL`, Postgres in prod, SQLite for dev/test:

- `demo/db.py` — `make_engine` / `make_session_factory`, same signatures.
- `demo/models.py` — one model per table in `supabase/migrations/`, kept in
  sync with the SQL by a test.
- `requirements.txt` — `sqlalchemy`, `psycopg[binary]`. **This ends the
  stdlib-only container by design**: the Dockerfile gains a pip step. The
  *foundry kit* stays stdlib-only (its contract is unchanged); the operator
  simply outgrows that rule for its persistence dependency, the way wall-e
  already did.

No RLS policies carry access control: the backend connects with the database
role (or service_role over the API, unused) and **is the only database client**
— the storefront never talks to Supabase directly, so no anon-key tables, no
per-row policies to get wrong. RLS stays enabled with deny-by-default as a
second lock on the door.

### 2. One table per file, keys preserved

`supabase/migrations/20261015000000_operator_schema.sql` maps each file under
`OPERATOR_DATA_DIR` to a table (§5 of the backend inventory: players, users,
sessions, settings, promos, plays, rounds, books postings, crash_pending,
asaas_charges, exclusions, scheduler receipts, integrity ledger):

- **Ids stay strings.** `player_id`, idempotency `key`, bearer `token` keep
  their current shapes — no UUID migration, no caller changes.
- **Money stays integer.** All minor-unit columns are `BIGINT`; no floats
  anywhere near the ledger.
- **Idempotency becomes constraints.** `books_postings.key` is the primary key
  (today: the in-memory `_keys` set); `asaas_charges.deposit_id` likewise.
  A retried POST becomes a constraint conflict, not a second posting.
- **Timestamps are `timestamptz`.** The JSONL `ts` strings parse into these.
- **Fresh start, no data migration.** Render free is ephemeral — live `/data`
  dies on redeploy anyway, so the cutover provisions empty tables. The
  migration tooling is the schema itself; there is no JSONL import path to
  build, test, or get wrong.

### 3. The storefront goes to Vercel as a server app, proxied — not exported

`web/` is currently `output: "export"` with dev-only `rewrites()` that Vercel
would silently ignore (static hosts have no proxy), which would leave every
`fetch("/api/…")` hitting Vercel static and dying. Two ways to fix it:

- (a) static export + `NEXT_PUBLIC_API_BASE` + backend CORS allowlist, or
- (b) Vercel server app whose `rewrites()` proxy `/api`, `/g`, `/rgs` to the
  backend, keeping every fetch relative and same-origin.

(b) wins and it is not close: no `api.js` changes, no CORS surface on the money
paths, `SameSite=Lax` game cookies and the Spribe `postMessage`
`window.location.origin` checks keep working unchanged, and the backend's
`_same_origin` gate never fires because the browser never leaves the Vercel
origin. So `web/next.config.js` becomes env-driven: `output: "export"` stays
the default (local dev, Docker image, `verify.py`'s `web/out` freshness check
all keep working), and on Vercel (`process.env.VERCEL` set, or explicit
`NEXT_OUTPUT=server`) it serves as a Node app with `rewrites()` pointing at
`BACKEND_URL`.

Two consequences, both recorded, neither blocking:

- **Preview deployments can't do bot-gated auth.** Turnstile hostnames are
  exact; each Vercel preview gets its own `*.vercel.app` host, which is neither
  on the widget's Domains nor in `TURNSTILE_HOSTNAMES`. Production
  (`<project>.vercel.app`, stable) is registered; previews exercise everything
  except login/signup, or point at a backend with the gate off.
- **`web/out` stays the container's fallback.** The Docker image still builds
  and serves the export, so the backend is self-sufficient if Vercel is down;
  `verify.py`'s freshness check is untouched.

### 4. Cutover order

1. Schema + seam land with files still the default (this change). All suites
   green; nothing reads Postgres yet.
2. Port stores one at a time behind `DATABASE_URL` (settings → sessions/users
   → players → books/rounds → the rest), each with its tests running on SQLite
   and a Supabase staging schema for the real thing.
3. Frontend to Vercel against the Render backend (rewrites proxy), Turnstile
   + widget Domains gain the Vercel host, Asaas webhook stays on the backend.
4. Backend reads/writes flip to Supabase; file paths retire; live-verify
   against `/api/health` exactly as in 0045/0047/0048.

## Alternatives considered

1. **Supabase Auth replacing `demo/auth.py`.** Tempting, but player auth is a
   `player_id` in localStorage (no bearer) and painel auth is a bespoke bearer
   store — neither maps onto Supabase Auth without changing every client call
   site. Revisit only if a second client (mobile app) needs real tokens.
2. **PostgREST for reads.** Adds a second API surface with its own auth story
   for zero benefit while one Python process owns all logic.
3. **Keep files, add a disk (Fly volume / Render paid).** Fixes durability
   without Supabase, but answers neither the hosting split nor the single-file
   locking ceiling. Fly keeps `/data` on a volume already (`fly.toml`) — the
   migration is about getting *off* files, not about where files live.
4. **Static export on Vercel + CORS.** Rejected in §3: it opens every money
   route to cross-origin traffic and requires re-proving the cookie/iframe
   posture. The rewrite proxy keeps the security shape identical.

## Notes

- Runbook: `docs/supabase.md`. Credentials: gitignored `.env.supabase`
  (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
  `DATABASE_URL`) — same never-in-chat flow as `.env.resend`/`.env.turnstile`.
- `TURNSTILE_HOSTNAMES` will gain the Vercel production host at phase 3; the
  widget's Domains in the Cloudflare dashboard must list it too.
- The Asaas webhook URL stays the backend's (`cadiback.onrender.com` or its
  successor) — Vercel never sees provider traffic.
