-- Decision 0071: account identities and revocable device sessions survive deploys.
-- Account snapshots preserve all existing profile fields, including password
-- hashes, session epochs, preferences and test-account settings. Revisions
-- reject stale writers instead of silently undoing a password reset/deletion.
CREATE TABLE IF NOT EXISTS identity_documents (
    name TEXT PRIMARY KEY,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    revision BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS player_devices (
    session_id TEXT PRIMARY KEY,
    player TEXT NOT NULL,
    epoch BIGINT NOT NULL,
    created BIGINT NOT NULL,
    seen BIGINT NOT NULL,
    expires BIGINT NOT NULL,
    remember BOOLEAN NOT NULL,
    user_agent TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_player_devices_player ON player_devices (player);
CREATE INDEX IF NOT EXISTS ix_player_devices_expires ON player_devices (expires);
ALTER TABLE identity_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE player_devices ENABLE ROW LEVEL SECURITY;
-- No anon/authenticated policies: only the trusted backend database role.
