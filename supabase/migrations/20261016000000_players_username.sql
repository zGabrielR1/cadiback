-- 0050: players get a username — the handle chosen at signup and used to log in.
--
-- Applied after 0049's schema. The players table is still empty (fresh start,
-- no data migration; the file store is the live one until the players store is
-- ported), so the column lands NOT NULL with an empty default and a
-- case-insensitive unique index. `Ana` and `ana` are the same account: the
-- backend stores the handle lowercased and resolves logins the same way.
--
-- Apply: Supabase dashboard > SQL editor (or `supabase db push`).

ALTER TABLE players
    ADD COLUMN IF NOT EXISTS username TEXT NOT NULL DEFAULT '';

-- Partial: an empty username (a legacy/test row that predates the handle) must
-- not collide with another empty one, but a real handle is unique on its own.
CREATE UNIQUE INDEX IF NOT EXISTS players_username_lower_key
    ON players (lower(username)) WHERE username <> '';
