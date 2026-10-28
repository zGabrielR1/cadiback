# 0098 — Share filtered public match views

Copied match links now include the current market category and search, allowing
another visitor to reopen the same public view. Default filters keep the short
match-only URL. Private “Minhas seleções” mode, slip contents, credentials,
unrelated query parameters and anchors are excluded.

Market filter parsing accepts only known categories and limits searches to 200
characters, rejecting control characters. Browser initialization occurs after
mount, keeping the static export independent of browser state. Navigating to a
different match or back to the board removes the previous match's URL filters.
Filters still survive feed refreshes; no quotes or bets are submitted by sharing.

Validation covers URL round trips, malformed input, privacy exclusions and
navigation cleanup. The controlled market-finder browser script also copies a
filtered link and opens it afresh for guests/members at four viewport widths.
No deployment is included.

Results: production build and verifier pass; eight Node test files, core 50/50,
backend 426/426 and controlled browser 408/408 pass. Dependencies restored in
web/node_modules and an isolated /tmp Python environment.
