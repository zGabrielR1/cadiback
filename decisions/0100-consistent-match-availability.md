# 0100 — Consistent availability across sports screens

The board and advanced builder allowed selecting prices from postponed,
cancelled, suspended or abandoned matches even though detail and slip checks
already paused them. Board prices also remained actionable after a failed feed
refresh. The server still checked placement, but the discovery UI contradicted
the review step.

`matchState` in `web/lib/sports.mjs` now supplies shared live/final/unavailable
classification, Portuguese labels and selection eligibility. Unavailable states
take precedence over embedded live/final hints. Existing handling of otherwise
unknown/unspecified statuses remains unchanged; this does not invent new server
contracts. The slip consumes the same classification.

- Board rows show Adiada/Cancelada/Suspensa/Abandonada above the team names
  (the narrow clock column keeps a dash) and disable prices while
  preserving details, favorites and existing selections. Extra markets use the
  same rule. Failed refreshes and in-flight updates pause board/featured prices.
- Highlights and upcoming-date discovery exclude unavailable matches. All-date
  discovery retains them for consultation; saved favorites remain saved.
- Public detail and the context panel show the actual unavailable status.
- Advanced builder uses the same labels and disables adding/transferring draft
  selections. Draft contents and removal stay available; resumed play restores
  controls after a successful feed refresh.

Unit checks cover status precedence, discovery filtering and slip recovery.
`scripts/check_match_availability.mjs` exercises controlled guest/member flows
at 1440/768/390/320: board-to-detail consultation, keyboard favorites, unavailable
highlights, feed failure/retry, builder draft preservation/removal and resume.
Every API response is stubbed, including the existing member settlement poll.
The floating slip is collapsed for consultation during these checks.

No live transactions, deployment or backend contract changes are included.

Results: production build, verifier0, nine Node test files, core50/backend426,
availability browser376 and market-finder browser408 pass. Desktop/phone
status labels and tablet builder layouts reviewed in both themes.
