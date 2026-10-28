# 0096 — Review live price changes in the betslip

## Problem

When the sports feed changed a selected price, selectionAvailability disabled
confirmation. Only server-preflight quote changes had an acceptance action, so
feed-driven changes required removing and reselecting the bet.

## Behavior

- Show selected and updated prices beside each changed selection, with a review
  panel comparing the combined price and potential return at the current stake.
  No combined-return estimate is offered while a selection is unavailable.
- The main slip action takes focus and scroll position to the review, rather
  than leaving an unexplained disabled confirmation button. Unavailable markets
  have their own review/recovery action and can be removed without clearing
  the remaining slip.
- Explicit price acceptance changes only the prices of existing selection
  identities. It preserves fixture/market/line/selection identity, metadata and
  stake. It never sends a quote request or a bet. Invalid and foreign price
  updates cannot introduce or replace selections.
- Accepting feed prices is disabled during refresh, failed feed updates, or a
  busy operation. Failed updates offer a retry from the review panel.
- Placement remains a separate action and retains the existing server quote
  preflight, explicit server-price acceptance, request-id retry and receipt flow.
  Accepting a server quote refreshes the board to resolve its older snapshot.
  Feed comparisons are hidden during server quote review to avoid presenting
  conflicting proposed prices. Explicit slip edits reset the old request id.

## Validation

Frontend unit cases cover identity/metadata preservation, unavailable legs,
unchanged inputs, malformed prices and foreign identities. Controlled browser
checks exercise increases/decreases, old/new combined price and payout, focus
and scrolling, explicit acceptance without submission, server rechecks and
mocked receipts, mixed/unavailable markets, removing the entire unavailable
slip, feed failure/retry, and desktop/mobile themes. No live transactions.

scripts/check_odds_review.mjs runs these checks against web/out served on
127.0.0.1:8784 or OPERATOR_QA_URL. Supply Playwright via module resolution or
PLAYWRIGHT_MODULE; CHROME_PATH optionally selects an installed browser. Time is
controlled to exercise normal feed polling without changing production cadence.
Screenshots are written to /tmp/operator-odds-review-qa.

This is a local frontend change; it does not deploy, create archives, change
backend acceptance rules, or add real-money/provider operations.
