# 0073 — Public sports, signed-in casino UI

Sports is the initial storefront view. Anonymous visitors can browse fixtures,
search teams and assemble a betslip; placing a bet still uses the existing login
flow. A dismissible lower-left invitation opens login without obscuring the
entire sports page. Desktop and mobile navigation put sports first.

Casino navigation opens login for guests and remembers the requested category
within that page. CasinoHome, game panels, details and publisher theater render
only when the current player has a matching, server-verified profile. Losing
that session clears open casino state and returns its view to sports. No new
backend casino access rule is introduced: this is explicitly a UI restriction.
Sports search stays in sports instead of routing to the casino; the sports feed
loads immediately on entry and then refreshes every 15 seconds.

The shared storefront uses slate surfaces, mint accents, calmer navigation,
larger sports typography, refreshed cards/forms and responsive guest entry.
Existing light mode, reduced-motion preferences and keyboard focus remain.

Deployment includes decisions 0071 and 0072. The live free Render instance has
one non-test account in files, no financial/game activity, and no shell/export
facility. Do not replace its identity with an empty database without a snapshot
or the owner's explicit approval of losing that account. Saved Vercel tokens
resolve to an account without access to cadiback-web; deployment needs the
owning account or its Git integration. Credentials and unrelated untracked
artifacts must not be committed.

Follow-up reliability pass: sports polling now retains the last successful board,
shows an error/retry and update time, refuses malformed payloads and ignores late
responses after leaving sports. Polls run sequentially. Dialogs trap keyboard
focus, restore the opener, lock scrolling and close with Escape; details are
included. Logout clears local UI immediately while server revocation finishes.
HTML/malformed-JSON API refusals retain HTTP status for session-expiry handling.
Public deployments remain unchanged pending the documented cutover/access gates.
