-- 0049: the operator's file state as Postgres tables (fresh start, no import).
--
-- One table per file that lived under OPERATOR_DATA_DIR (see the backend
-- inventory: demo/server.py DATA + frame/wallet/books.py + demo/auth.py +
-- frame/compliance/sigap.py + frame/ops/scheduler.py + frame/core/ledger.py).
--
-- Rules held throughout:
--   * ids stay TEXT in their current shapes (player-..., idempotency keys,
--     bearer tokens) — no UUID migration, no caller changes;
--   * money is BIGINT minor units everywhere — no floats near the ledger;
--   * idempotency is a PRIMARY KEY / UNIQUE constraint, not application memory
--     (books_postings.key replaces the in-memory _keys set);
--   * timestamps are timestamptz; the JSONL ts strings parse into these;
--   * the backend is the ONLY database client (service/database role, RLS
--     deny-by-default below). The storefront never talks to Supabase directly.
--
-- Apply: Supabase dashboard > SQL editor, or `supabase db push`. Verify with
--   select table_name from information_schema.tables
--    where table_schema = 'public' order by 1;

-- Player profiles (players.json). Secrets live here; _public_profile strips
-- them at the API boundary, so no column-level games — the API never selects
-- pw_hash/pw_salt/pix_raw into a response.
CREATE TABLE IF NOT EXISTS players (
    player_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    cpf_masked  TEXT NOT NULL DEFAULT '',
    pw_hash     TEXT NOT NULL,
    pw_salt     TEXT NOT NULL,
    pix_kind    TEXT NOT NULL DEFAULT '',
    pix_masked  TEXT NOT NULL DEFAULT '',
    pix_raw     TEXT NOT NULL DEFAULT '',
    bank        JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_test     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS players_created_at_idx ON players (created_at);

-- Painel admin credentials (users.json).
CREATE TABLE IF NOT EXISTS users (
    username    TEXT PRIMARY KEY,
    pw_hash     TEXT NOT NULL,
    pw_salt     TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'viewer'
);

-- Painel bearer sessions (sessions.json). TTL is swept by the backend, exactly
-- as SessionBook does today; expires_at is indexed for the sweep.
CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    username    TEXT NOT NULL REFERENCES users (username) ON DELETE CASCADE,
    role        TEXT NOT NULL DEFAULT 'viewer',
    issued_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expires_at_idx ON sessions (expires_at);
CREATE INDEX IF NOT EXISTS sessions_username_idx ON sessions (username);

-- Operator toggles (settings.json). Only diffs from SETTINGS_DEFAULTS are
-- stored; value is JSONB so booleans/strings/numbers keep their types.
CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL
);

-- Per-player promotion state (promos.json): bonus_event, welcome_claimed,
-- cashback_days. Opaque to SQL — the bonus engine owns the shape.
CREATE TABLE IF NOT EXISTS promos (
    player_id   TEXT PRIMARY KEY REFERENCES players (player_id) ON DELETE CASCADE,
    state       JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Presentation-only game opens (plays.jsonl). Never money; append-only.
CREATE TABLE IF NOT EXISTS plays (
    id          BIGSERIAL PRIMARY KEY,
    game_id     TEXT NOT NULL,
    player      TEXT NOT NULL DEFAULT '',
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS plays_game_ts_idx ON plays (game_id, ts);

-- Round ledger (rounds.jsonl). Settlement appends a SECOND row with the same
-- round_id, so round_id is deliberately NOT unique — (round_id, ts) orders a
-- round's life. A bet is idempotent by (round_id, tier): one 'pendente' row and
-- at most one settled row per round.
CREATE TABLE IF NOT EXISTS rounds (
    id              BIGSERIAL PRIMARY KEY,
    round_id        TEXT NOT NULL,
    player          TEXT NOT NULL,
    game_id         TEXT NOT NULL,
    stake_minor     BIGINT NOT NULL DEFAULT 0,
    payout_minor    BIGINT NOT NULL DEFAULT 0,
    tier            TEXT NOT NULL DEFAULT '',
    type            TEXT NOT NULL DEFAULT '',
    ts              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS rounds_round_id_idx ON rounds (round_id);
CREATE INDEX IF NOT EXISTS rounds_player_ts_idx ON rounds (player, ts);

-- The money source of truth (books.jsonl). key is the idempotency key: a
-- retried POST becomes a constraint conflict, never a second posting. legs is
-- the balanced journal entry [{account, amount_minor}], owned by frame/.
CREATE TABLE IF NOT EXISTS books_postings (
    key         TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    legs        JSONB NOT NULL,
    seq         BIGSERIAL UNIQUE NOT NULL,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS books_postings_ts_idx ON books_postings (ts);

-- In-flight live crash positions (crash_pending.json). Boot voids leftovers
-- (refund), exactly as _void_crash does today.
CREATE TABLE IF NOT EXISTS crash_pending (
    token       TEXT PRIMARY KEY,
    round_id    TEXT NOT NULL,
    player      TEXT NOT NULL,
    stake_minor BIGINT NOT NULL DEFAULT 0,
    bonus_part  BIGINT NOT NULL DEFAULT 0,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pix charges (asaas_charges.json). deposit_id is the caller's idempotency id
-- (newDepositId); provider_ref is Asaas's. Confirmed exactly once.
CREATE TABLE IF NOT EXISTS asaas_charges (
    deposit_id      TEXT PRIMARY KEY,
    player          TEXT NOT NULL,
    amount_minor    BIGINT NOT NULL,
    provider_ref    TEXT NOT NULL DEFAULT '',
    provider_status TEXT NOT NULL DEFAULT '',
    qr_payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    posted          BOOLEAN NOT NULL DEFAULT FALSE,
    paid_at         TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS asaas_charges_provider_ref_idx
    ON asaas_charges (provider_ref);

-- Self-exclusion registry (exclusions.json, frame/compliance/sigap.py).
-- The record shape belongs to sigap; data stays opaque JSONB.
CREATE TABLE IF NOT EXISTS exclusions (
    player      TEXT PRIMARY KEY,
    data        JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Scheduler receipts (sched/latest.json) + fan-out counters
-- (notify_count.json, notify_cooldown.json). Receipts append; counters upsert.
CREATE TABLE IF NOT EXISTS sched_receipts (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    tier        TEXT NOT NULL DEFAULT '',
    screened    INTEGER NOT NULL DEFAULT 0,
    passed      INTEGER NOT NULL DEFAULT 0,
    notified    INTEGER NOT NULL DEFAULT 0,
    errors      JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE TABLE IF NOT EXISTS sched_counters (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL
);

-- Integrity hash chain (ledger.jsonl, frame/core/ledger.py). Currently written
-- by nothing and read by /api/health; the table exists so the health check has
-- a home after the cutover instead of a missing file.
CREATE TABLE IF NOT EXISTS ledger (
    id          BIGSERIAL PRIMARY KEY,
    prev_hash   TEXT NOT NULL DEFAULT '',
    hash        TEXT NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Second lock on the door: RLS on, no public policies. The backend connects
-- with the database role and is the only client; the anon key can reach the
-- API but no table through it.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'players', 'users', 'sessions', 'settings', 'promos', 'plays',
        'rounds', 'books_postings', 'crash_pending', 'asaas_charges',
        'exclusions', 'sched_receipts', 'sched_counters', 'ledger'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    END LOOP;
END
$$;
