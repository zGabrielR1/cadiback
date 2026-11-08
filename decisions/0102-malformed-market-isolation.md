# 0102 — Isolate malformed provider markets

Date: 2026-10-28

## Decision and evidence

A broad automation run compared three directions:

| Direction | User problem and evidence | Outcome / dependencies | Effort and risk | Acceptance |
| --- | --- | --- | --- | --- |
| Malformed market isolation (selected) | validMarkets throws on null entries and non-array collections; consumed by sports board/detail and casino recommendations | Ignore malformed market entries, retain healthy siblings; existing helper only | Small, low regression risk | Reproductions return empty/healthy lists, valid object identity/order unchanged |
| Availability rule changes | Unknown status currently permits selection; whether every provider needs this fallback is unverified | Requires provider contract evidence before changing eligibility | Medium; could suppress legitimate markets | Agreed provider status contract and fixtures |
| Deployment workflow repair | Latest release record reports Fly trial billing blocker | Requires owner billing/environment decision | External dependency | Successful authorized deployment |

The selected defect has an executable oracle. No arena fan-out or new product behavior is needed. This run changes only the shared market helper, regression tests and continuity records.

## Behavior and acceptance

Missing fixtures and non-array market collections return an empty list. Null/undefined market entries are discarded. Every outcome must be a nonblank string; reject the entire malformed market rather than shifting outcomes relative to prices. Accepted strings are preserved exactly. Healthy siblings retain reference, order and prices. Existing incomplete/nonnumeric/invalid-price rejection remains unchanged. No mutation, fabricated fallback prices or API writes.

## Verification and skeptical review

Confirmed the two TypeErrors before editing. Checked all three UI call sites for reachability. Regression cases cover malformed collections, mixed entries and preservation of a valid sibling; all 41 JavaScript tests across nine files pass when run directly. Production static export passes. Structure verifier: zero problems. Core: 50/50. Scoped git diff --check passes.

Backend: 426 run, 393 pass, 33 errors: six missing SQLAlchemy and 27 local HTTP socket PermissionErrors in this sandbox. Installing requirements into /tmp/operator-validation-venv failed PyPI DNS resolution. These are validation limits, not passing backend evidence. No browser/visual review, deployment or live account/payment mutations performed.

Review conclusion: helper behavior CONFIRMED by execution; full release readiness remains conditional on backend gates. The patch does not claim to sanitize every possible fixture field or every direct market consumer. Review found no API, pricing, ledger or layout changes, unrelated edits, or secrets in the patch. No harness mutation warranted.

## Handoff

Rerun backend gates with dependencies and socket access before publication. Preserve pre-existing tooling deletions and probes/flashscore-cache.json changes. For future sessions, restore frontend dependencies with npm ci; this checkout initially lacked web/node_modules and web/out. Direct execution of the nine test files exposes individual test counts under the installed Node version.

## Follow-up verification, 2026-10-28

Found the cached Python environment at /home/pwdmcl/.cache/uv/archive-v0/7JRctxnJXeuaNP7w/bin/python (3.12.15, SQLAlchemy 2.1.6, psycopg 3.3.6). Re-executed demo.test_demo: 426 run, 399 pass, 27 errors, exclusively sandbox HTTP socket PermissionErrors. The six missing-SQLAlchemy errors from the initial run are resolved. This does not satisfy the full backend gate.

Executed demo.test_persistence, demo.test_signup_cashier and scripts.test_render_deploy: 41 run, 28 pass, 13 Postgres cases skipped because OPERATOR_TEST_DATABASE_URL is unset. Database persistence checks use isolated SQLite, not a live Postgres service.

Added a real betslip helper integration regression for malformed-market disappearance and recovery: only the affected selection becomes unavailable; other selections and saved prices are preserved; recovered prices require explicit acceptance. Ran it against the original HEAD helper in a temporary copy: it fails with the original null-market TypeError. With the patch, all 42 JavaScript tests across nine files pass. Rechecked core 50/50.

Skeptical review: failure-to-pass comparison validates the regression; frozen saved selections verify non-mutation. Healthy markets keep their original references, and no automatic acceptance or submission occurs. Remaining HTTP cases cannot be represented as passing without actual socket access. No additional production-code change or harness mutation was needed.

Final follow-up gates: fresh npm run build passes, python scripts/verify.py reports zero problems, scoped git diff --check passes. Existing static-export rewrite warning remains; this patch does not change routing.

## Component verification and outcome contract, 2026-10-28

Created scripts/check_market_render.cjs to execute the actual SportsHome, MarketDetail and BetBuilder JSX with the installed Next SWC compiler and React static rendering. Reproduced an additional failure: a market with selections ['Casa', {}, 'Fora'] and valid prices passed validation, then React threw “Objects are not valid as a React child.” This is within malformed-market isolation; frame/verticals/sports/contract.py defines Market.selections as tuple[str, ...].

The guard now requires each selection to be a nonblank string, discarding the whole market on a bad label. It does not stringify provider objects or trim valid identities, drop individual outcomes, shift prices, or alter selection metadata. Numeric strings and accented/padded labels retain their exact values. A frozen-input regression covers object/array/null/undefined/numeric/boolean/blank labels and valid sibling preservation. The betslip disappearance/recovery regression also covers object/blank outcomes.

The new smoke command is node scripts/check_market_render.cjs (Node 22.12+, installed web dependencies). It passes 55 static component renders across 11 feed variants: public/member sports board and details, member builder, missing markets and malformed entries/outcomes, healthy sibling preservation and existing empty states. Limit: no effects, hydration, event handling, responsive layout or browser execution. Casino recommendations are not covered by this render command because their feed arrives through an effect. No live APIs are used.

All 43 individual JavaScript tests pass across nine files. Fresh production export and core 50/50 pass. Skeptical review confirmed the UI-level failure before extending validation, and that rejection is market-wide with original label/price identities retained. New script uses the installed Next compiler without adding packages or affecting product runtime; it must be rechecked when Next or Node changes.

Final component-cycle checks: structure verifier zero problems; scoped diff check clean; backend rerun 426 tests, 399 pass, 27 HTTP-binding PermissionErrors. Implementation and local component acceptance are complete; publication still needs the restricted HTTP checks. No browser/visual QA or deployment performed. Existing unrelated deletions/cache edits remain untouched.
