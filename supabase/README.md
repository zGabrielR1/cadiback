# supabase/

The operator's database as SQL. One migration per schema change, named like
the Supabase CLI expects (`YYYYMMDDHHMMSS_name.sql`).

## Apply

Supabase dashboard > SQL editor > paste the migration > Run. Or with the CLI:

```bash
supabase db push
```

Fresh start: the schema provisions **empty** tables (decision 0049 — Render
free is ephemeral, so there is no live data worth importing).

## Verify

```sql
select table_name from information_schema.tables
 where table_schema = 'public' order by 1;
-- players, users, sessions, settings, promos, plays, rounds,
-- books_postings, crash_pending, asaas_charges, exclusions,
-- sched_receipts, sched_counters, ledger
```

## Layout

```
migrations/   20261015000000_operator_schema.sql — the fourteen tables
```

`demo/models.py` is the same schema as SQLAlchemy models; `DbSeamTest` fails
if the two drift apart.
