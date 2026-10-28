# 0094 — Shareable public match detail

## Problem and choice

Public match detail existed only in SportsHome state: reloading lost the match,
and there was no link to share. Use a `match` query parameter containing the
existing feed fixture key. This works with the current static export and reuses
the existing public detail rather than adding server routes or a second feed.

## Behavior

- Opening detail creates a browser history entry. Direct links and reloads open
  that match, and Back/Forward synchronizes the view. Returning to sports through
  the header clears the match identity. Returning from detail restores the board
  origin's focus/scroll when available.
- Copy link includes only the current origin/path and encoded match identity.
  Other query parameters and hashes are omitted, so authentication fragments and
  unrelated URL state are not shared. Clipboard denial exposes a selectable link.
- The initial feed request shows loading, request failure offers retry, and a
  successful feed without that fixture explains its absence. The link identifies
  current feed data; it does not promise historical fixture retention or frozen
  prices. Existing authentication and selection rules remain in effect.
- Entering advanced research clears the match URL. Browser Back can reopen detail
  and returning from there shows the sports board rather than a stale builder.

## Validation

Production static export, structure verifier, core 50/50, backend 426/426, and
seven frontend Node test files pass. Browser regression checks use controlled
feed/session API responses at 1440/768/390/320, plus authenticated dark-mode
selection/research navigation at 1440/390. No live accounts or payment/bet writes.
Screenshots of desktop and mobile fallback states were visually reviewed.

The browser regression script is `scripts/check_match_links.mjs`. Serve `web/out`
on 127.0.0.1:8784 (or set OPERATOR_QA_URL), provide Playwright through the module
resolution path or PLAYWRIGHT_MODULE, and optionally set CHROME_PATH. Its API
interception makes these UI checks independent of the real backend. Browser
screenshots are written to /tmp/operator-match-qa.
