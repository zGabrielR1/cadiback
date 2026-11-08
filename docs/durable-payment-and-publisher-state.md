# Durable crypto invoices and publisher state

Implemented locally 2026-11-08. **Real SQL integration verification remains pending.** The full release gate still reports 6/14 passing stages; do not treat this implementation as a verified cutover.

## Database documents

With an injected database session factory, `crypto_charges` stores pending/paid crypto invoice metadata in `IdentityDocument`. All crypto create, status and IPN lookups use the shared document rather than a process cache. Invoice identity (owner, amount, provider reference) cannot be reassigned, and stale pending writes cannot downgrade a paid acknowledgement. Credit and the paid marker share the wallet transaction.

`publisher_state` stores wallet tokens, publisher-session bindings, accumulated round stakes/wins, and Pragmatic publisher balance baselines and sequence numbers. Provider/session identities are serialized as explicit records, preserving tuple identities even when strings contain delimiters. All publisher entry points refresh under the wallet lock and save once per outer operation. Nested calls share state; failed writes/commits restore the refreshed cache.

The RGS response tap accumulates, closes, settles and saves pending state under one operation. A durable settlement refusal propagates so pending state is retained rather than silently discarded. Pragmatic movement state rolls back with a failed durable settlement. Publisher-session rebinding to a different wallet is rejected.

## Lock order

Publisher operations acquire `_publisher_lock` before `books.lock`. Nested publisher calls reuse the current operation. `wallet_credit` deliberately places `@publisher_method` outside `@durable_wallet_operation`; preserve that order. Provider HTTP calls stay outside these locks. Crypto operations acquire their rail lock before the shared wallet transaction; the store joins the current wallet session.

## Backups and cutover

Wallet backup/export/restore now includes optional `crypto_charges` and `publisher_state` documents, validates their shape, and continues to read older wallet backups without those optional documents. Explicit file import includes `crypto_charges.json`; database mode never implicitly imports legacy crypto files. Publisher state had no legacy file snapshot to import.

New backup files use exclusive creation and mode 0600 on POSIX because publisher tokens are bearer credentials. Both manual and pre-deploy backups validate the written file. Existing files are not overwritten.

This remains a wallet/runtime backup, not a complete identity/provider database backup: the separate `asaas_charges` SQL table is not exported by this utility. Existing publisher token lifetime/cleanup rules are unchanged. Provider request deduplication beyond journal settlement keys still needs review.

## Verification

- Offline checks cover publisher JSON round trips, delimiter-safe identities, nested-state orchestration, restoration after operation/save/commit errors, malformed state, private backup files, invoice-reference conflict refusal and failed acknowledgement retries.
- Backend discovery reports 468 tests: 433 pass, 35 environment errors (8 missing-SQLAlchemy/import errors and 27 prohibited sockets). Tests inside failed SQL modules did not execute.
- Release-tool discovery: 36 tests pass. Core: 50 pass. Frontend: 14 Node files pass. Auth: 3 Node files pass. Static Render preflight and Docker context pass.
- Added SQL regressions cover fresh-directory crypto invoice/paid-marker persistence, crypto acknowledgement rollback, monotonic Pix acknowledgements, publisher handoff, failed-tap rollback, Pragmatic baseline continuity, concurrent stake accumulation, and backup/restore of the new documents. SQLite and isolated Postgres execution remain required.

Latest stage evidence: `.release/report.json` and `.release/*.log`; full environment blockers and rerun instructions are in [the release report](release-verification-2026-11-08.md). No live database/provider writes, publication, commit or push occurred.
