-- 0057: the painel's win/loss dial, per player.
--
-- Applied after 0050's username column. The players store is still file-backed
-- (the live one until it is ported, decision 0049), so the columns land with
-- defaults and no data migration. `outcome_bias` is one of normal /
-- always_win / always_lose / win_rate; `win_rate_percent` is the whole-percent
-- win share a `win_rate` bias targets.
--
-- Apply: Supabase dashboard > SQL editor (or `supabase db push`).

ALTER TABLE players
    ADD COLUMN IF NOT EXISTS outcome_bias TEXT NOT NULL DEFAULT 'normal';

ALTER TABLE players
    ADD COLUMN IF NOT EXISTS win_rate_percent INTEGER NOT NULL DEFAULT 100;
