# Release verification — 2026-11-08

Status: **NOT APPROVED FOR RELEASE**. All 14 stages were attempted; 6 passed and 8 failed or could not complete. No verified receipt was issued. The source fingerprint remained unchanged throughout the final run.

Source SHA-256: `9e83f8499586253f9a409b05fac764b00fab938073c2ca3cd9f4a4bebdd4cba5`

Machine-readable evidence: [report](../.release/report.json); each stage has a corresponding `.release/<stage>.log`. These local artifacts are ignored by Git. CI now uploads the report and stage logs on completion.

| Stage | Result | Evidence / limitation |
| --- | --- | --- |
| Postgres configuration | Blocked | No explicit isolated `OPERATOR_TEST_DATABASE_URL`; production database credentials were not substituted. |
| Core | Pass | 50 tests. |
| Backend discovery | Incomplete | 468 tests reported, 35 errors: 8 missing-SQLAlchemy/import errors and 27 prohibited local-socket errors. The remaining 433 reported tests passed; database modules that could not import did not execute their contained regressions. |
| Release tooling | Pass | 36 tests, including real temporary-Git-repository and subprocess checks. |
| Frontend | Pass | 14 Node test files. |
| Auth sidecar | Pass | 3 Node test files. |
| Frontend production dependency audit | Blocked | npm registry DNS failure; no vulnerability-free claim. |
| Auth production dependency audit | Blocked | npm registry DNS failure; no vulnerability-free claim. |
| Frontend build | Blocked | Locked Next dependency unavailable locally; `next` executable missing. |
| React component rendering | Blocked | Next SWC dependency unavailable. |
| Render preflight | Pass | 11 required files, zero structural problems. |
| Docker context | Pass | Static committed-tree context check, 1,311 included files; no container image build was performed. |
| Structure/export | Blocked | Two findings, both caused by missing `web/out/index.html`. |
| Browser QA | Blocked | Locked Playwright executable unavailable; no new browser/viewport QA claimed. |

## Problems fixed during this verification

- The release runner previously stopped at the first failing command and could leave a prior successful receipt usable after a failed rerun. It now revokes old receipts first, attempts every stage, writes individual logs and an atomic JSON report, bounds commands, rejects empty runs, and issues approval only after every stage passes with unchanged source.
- Backend/script test discovery replaces the hand-maintained module subset. The fingerprint now includes Docker ignore rules, Git ignore rules, workflows and non-cache provider/catalog sources. Both web and auth production dependencies receive audit stages; Render and Docker context receive explicit static stages.
- CI previously skipped all opt-in Postgres integration coverage. It now provisions an isolated Postgres 16 service, supplies the test-only URL and retains verification artifacts. **This updated workflow has not been executed remotely.**
- Deployment could back up the current database and then apply a different local `DATABASE_URL`. Environment planning now rejects database replacement/removal before configuration changes and backs up the actual planned target for an initial cutover. A new durable deployment requires a database URL.
- Render previously deployed the remote branch tip and could treat an older deployment as the result of a rejected trigger. It now requires committed verified source, sends the exact local SHA, tracks only the ID returned by that trigger, and rejects a mismatched commit. The terminal-state list also no longer treats an in-progress pre-deploy step as failure. This uses Render's documented [commitId parameter](https://api-docs.render.com/reference/create-deploy).
- Both deployment tools reject ignored source files that were verified locally but would be omitted from Git publication. Existing unrelated local edits were preserved.

## Dependency restoration attempts

Python installation into `/tmp/operator-venv` failed because the configured index returned no SQLAlchemy distribution. Offline npm installation from a copied cache failed because the locked Playwright 1.65.0 archive was absent. The cache contains older Next/Playwright archives, which were not substituted for the locked release versions. Package manifests and lockfiles were not changed during this verification.

## Deposit durability continuation

- Daily deposit limits now sum the player's posted deposits for the current UTC day. Restarted workers use the same journal as active workers; replays, withdrawals, bonuses and other players cannot reset or distort the deposit total. Invalid/timezone-free deposit timestamps fail closed.
- Asaas charge reads/writes now join the wallet transaction when one is active; confirmation flushes the credited marker with the wallet posting. Caller-visible success is set only after commit. SQL rollback verification remains pending.
- File-backed Asaas/crypto acknowledgements publish their in-memory state only after a successful atomic file replacement. Failed writes remain retryable against the existing journal posting without double credit.
- Five new offline regressions pass, and the existing rollover test now advances the actual UTC clock instead of overwriting a process counter. Two additional database regressions cover concurrent-worker limits and failure after an Asaas acknowledgement flush; these could not execute without SQLAlchemy.
- Full gate rerun: 14 stages attempted, 6 passed, no approval. Backend discovery now reports 463 tests with the same 35 environment errors and no assertion failures. Focused deposit/round/crash tests: 14 pass.

Crypto invoice and publisher-session persistence are now implemented in shared database documents; SQL integration verification remains pending. See [the implementation and cutover notes](durable-payment-and-publisher-state.md). Wallet/runtime backup still does not replace a complete payment/identity database backup.

## Latest UI continuation

History search now matches accentless Portuguese names. Chat has accessible labels/live announcements, form submission, blank-send prevention, composition-safe Enter handling, Escape dismissal and a shrinkable input. Frontend tests pass; fresh JSX build and browser validation remain blocked. The owner authorized publication, but the attempted build lacked `next` and the Vercel helper refused an unverified release. No deployment occurred. The latest full gate still reports 6/14 passing stages against unchanged source.

## Required next run

In an environment with package registry access and local sockets:

1. Install `requirements.txt` into an activated Python environment.
2. Run `npm ci --prefix web` and `npm ci --prefix auth-server`.
3. Install the locked browser with `cd web && npx playwright install --with-deps chromium`.
4. Supply an isolated, disposable Postgres database as `OPERATOR_TEST_DATABASE_URL`. Tests create and remove their own unique schemas; do not use production as the test target.
5. Run `python scripts/release_gate.py`. Review every stage and the source-stability result in `.release/report.json`.

Durable crash/round rollback, concurrency, restart and backup/restore regressions still require real SQL execution. Real SQL verification, Asaas-table backup coverage, publisher token cleanup and provider request deduplication remain review areas. No live database/payment/account mutations, deployment, commit or push were performed in this verification.
