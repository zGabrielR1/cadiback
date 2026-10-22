# 0071 — Durable player identity and device sessions

## Problem

Device-session JSON disappears on ephemeral deployments. Persisting only its
rows is insufficient: a signed token also requires the player record and its
revocation epoch. Social links must survive alongside those accounts.

## Decision

Use the existing explicit `Demo(db=...)` seam. With a session factory, store
device rows in `player_devices` and account/social-link snapshots in
`identity_documents`. Without it, retain local files. Never implicitly import
files on startup: a stale backup must not restore deleted users or sessions.

The identity documents preserve the complete existing profile shape. They are
separate from the original unused `players` model, whose columns do not yet
represent the live profile contract. A revision check rejects stale writes
instead of undoing password resets, account deletion, or another signup.
This serializes account editing at the document level and is intentionally
sized for the current single-instance hobby platform.

Device creation and revocation use per-player Postgres transaction advisory
locks, including the first login with no rows. SQLite tests use an immediate
write transaction. Activity touches are conditional updates, never upserts;
revocation cannot be undone by a late touch. The owner, epoch and expiry must
match the signed token. The 20-device cap and 10-minute touch cadence remain.

`DATABASE_URL` supports the existing `envs/` credential layout, root overrides,
and exported-environment precedence. Bare Postgres URLs select the installed
psycopg 3 driver. A configured database failure or missing identity migration
fails startup rather than silently serving empty files.

## Cutover

Apply `supabase/migrations/20261022000000_persistent_identity.sql` to the
configured database. Stop account/session writes, take a snapshot of the
running instance's `players.json`, `oauth_links.json`, `player_sessions.json`,
and import with `python -m scripts.import_identity --data-dir <snapshot> --apply`.
Without `--apply`, this only validates local files and does not connect.
Import is one transaction, requires an empty destination, drops expired or
wrong-epoch device rows, and refuses subsequent imports. Preserve the signing
secret (`PLAYER_SESSION_SECRET` or `BETTER_AUTH_SECRET`) across the deployment.
Do not import a laptop snapshot over live production identity.

No automatic schema changes, imports, deployment, or signing-key rotation.
Both tables use RLS with no public policies. Credentials and token strings are
not written to the database session rows or diagnostics.

## Related storefront improvements

Remove `player` fields from all player action payloads: the session header is
the identity. Keep request error HTTP status, preserve stored login on network
failure, and clear profile/history on a confirmed 401. Ignore stale refresh
results after the browser credential changes. Session revocation controls
disable while pending and show inline errors. Malformed Unicode tokens receive
an authentication refusal instead of an encoding exception.

## Limits

The wallet/books, rounds, panel settings and other unported stores still use
files. This is identity persistence, not a complete durable-money cutover or
permission to run multiple wallet replicas. `/api/health` reports both identity
and wallet storage so the distinction is observable. Password reset requests
and in-flight OAuth handoffs are still temporary; the durable account epoch
and device revocations remain authoritative after a reset completes.

## Verification

The persistence suite exercises fresh deployment directories, password epoch
changes, deleted accounts, cross-instance revocation, stale account writes,
expiry, concurrent login caps, one-time import/rollback, and startup refusal.
It runs on scratch SQLite by default. Explicit `OPERATOR_TEST_DATABASE_URL`
enables the same checks in disposable Postgres schemas; no production rows
are read or changed. The frontend API tests cover header-only identity,
HTTP error status and browser credential storage.

Implementation references: [Postgres advisory locks](https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-ADVISORY-LOCKS),
[SQLAlchemy transaction contexts](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#framing-out-a-begin-commit-rollback-block).
