# 0103 — Reject malformed fixture refreshes before replacing working state

Date: 2026-10-28

## Decision and scope

Continue Operator production-readiness work after 0102. Compared three directions:

| Direction | Evidence / user problem | Outcome and dependencies | Effort / regression risk | Acceptance |
| --- | --- | --- | --- | --- |
| Validate fixture feed boundary (selected) | Actual SportsHome rendering of fixtures:[null] throws reading key; hook only checks outer array | Invalid payloads enter existing recovery path and preserve prior board; no external dependency | Small; overly strict validation could hide legitimate data | Preserve supported/optional fields and original identities, reject malformed refresh, retry restores feed |
| Finish backend HTTP gate | Latest runs identify sandbox socket PermissionErrors | Needs an environment permitting local HTTP binding | External execution constraint | Execute those tests successfully with real local HTTP |
| New discovery feature | Existing shared links/calendar/market finder are complete; no new request or proven gap selected | Requires further product evidence | Larger and speculative | Define a concrete user workflow first |

Selected an execution-proven failure, not a new feature. No arena or harness mutation is warranted. Existing 0102 changes and unrelated local edits remain intact.

## Contract and behavior

readSportsFeed accepts an object with a fixtures array. Each fixture must be an object with a unique nonblank string key, string home/away names, optional string sport/competition/country/status/progress/kickoff, and optional finite numeric scores. Optional fields may be absent or null. source/note metadata may be absent/null/string. Empty calendars, zero scores, blank team names and future sport/status strings remain valid; no allowlist or inferred kickoff/score is introduced.

Reject an entire malformed refresh rather than present partial data with a new successful timestamp. Return valid payloads exactly; preserve fixture/market references and all supplied labels/prices. Markets remain the responsibility of validMarkets (0102). This validator does not certify every optional nested field or all possible provider semantics.

useSportsFeed validates before setSports and setUpdatedAt. Rejection runs its existing error path: preserve the previous board/timestamp, clear loading, expose retry, and let existing feed-error gates pause selection. Initial invalid data stays an error rather than becoming a successful empty feed. Subsequent valid data, including an empty calendar, clears the error. CasinoHome uses the same reader in its independent fetch chain; rejection goes to its existing catch and preserves prior recommendations. Its existing polling/error presentation is otherwise unchanged.

## Verification

- Before editing: static rendering of actual SportsHome with fixtures:[null] throws TypeError reading key. Evidence: /tmp/operator-0103-baseline.log.
- Pure validator regressions cover invalid envelopes/metadata, malformed records and header fields, duplicate identities, optional fields, empty feeds, zero scores and identity preservation. Distinct healthy fixture keys ensure malformed-field tests cannot pass merely because of duplicate-key rejection.
- Hook tests execute the actual useSportsFeed body with controlled useState/useEffect/request/timer adapters. They cover previous-board/timestamp retention, retry and error clearing, malformed initial load, valid empty response, and request abort/late-response suppression after leaving the view. This is a unit effect-lifecycle test, not a mounted React/browser test.
- Ran the hook tests against original HEAD in an isolated temporary directory: the two malformed-feed tests fail; the cancellation test passes. Patched hook: all pass.
- All 50 JavaScript tests in 11 files pass. 63 actual static React renders pass via scripts/check_market_render.cjs, including public/member error/retry states, preserved board and paused/resumed odds controls, and existing market/builder cases. No effects, hydration, responsive layout or browser interactions are claimed by that command; casino fetch effects are not exercised there.
- The local historical Flashscore cache's 320 fixture headers pass validation. This is historical local compatibility evidence, not a live request.
- Fresh production static export and core 50/50 pass. Final backend/structure/diff results follow below.

## Skeptical review and handoff

Confirmed the failure at an actual render consumer, then confirmed the hook regression fails without validation. Optional fields and blank/missing facts remain supported; no unknown-status policy change was smuggled into validation. No identity coercion, label trimming, invented price, secret, API mutation or deployment is part of the patch. The request sequencing, cleanup and 15-second polling behavior remain in the existing hook. Remaining publication gates must be reported separately from component and unit test success.

## Final gate results

Production export passes. scripts/verify.py: 93 required files, 104 Python sources, zero problems. Scoped git diff --check passes. Backend demo.test_demo: 426 run, 399 pass, 27 errors, all sandbox local HTTP-binding PermissionErrors; no dependency errors. Logs: /tmp/operator-0103-{node,render,core,build,backend}.log. Full backend HTTP verification is still required before publication; this change is not deployed. No browser/visual QA, live account/payment mutation or harness mutation performed.
