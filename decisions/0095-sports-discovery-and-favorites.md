# 0095 — Cross-sport discovery and saved matches

## Problem

Favorites and search inherited the automatically selected sport, hiding saved
matches and search results in other sports. Removing filters could leave a
hidden live/sport restriction. Empty states did not distinguish an empty saved
collection, saved matches absent from the current feed, and filtered results.

## Behavior

- Add an explicit Todos os esportes choice to desktop and mobile navigation.
  The normal initial board keeps its existing automatic sport choice. Entering
  Favorites or beginning a search opens all sports and clears the old league.
  Subsequent explicit sport choices narrow the current collection/search and
  appear as removable filter controls. Clear-all removes sport and live filters.
- Search also recognizes Portuguese sport names such as basquete and tênis.
  Searching from match detail returns to the board and clears the match URL;
  casino search remains within its own view.
- Favorites lists saved fixture keys across sports, shows available/saved counts,
  scopes sport/live counts to the collection, and synchronizes localStorage
  changes across tabs. Saved keys absent from the current feed are retained.
- Empty collection explains how to save a match. Missing saved fixtures explain
  feed availability. Filtered favorites offer a recovery action that preserves
  Favorites. Ordinary empty search clears its filters and restores discovery.
- In the all-sports board, competitions are grouped and collapsed by country,
  sport and competition. Identically named competitions in different sports
  stay separate and carry their sport label.

## Validation and boundaries

Frontend unit coverage includes all-sport saved matches, absent saved keys,
Portuguese sport searches, accent handling, and explicit sport narrowing.
Controlled UI checks cover collection entry, narrowing, recovery, persistence,
cross-tab changes, missing/empty collection states, independent competition
collapse, long queries, detail-to-search navigation and both themes at four
viewport widths. Existing public match-link regression checks are also run.

Use scripts/check_sports_discovery.mjs with a static web/out server at
127.0.0.1:8784 or OPERATOR_QA_URL. Provide Playwright through module resolution
or PLAYWRIGHT_MODULE; CHROME_PATH optionally selects its browser executable.
Screenshots go to /tmp/operator-discovery-qa. API responses in these browser
checks are controlled fixtures, not evidence of live feed availability.

Favorites remain local to the browser; no account sync or historical feed
retention is introduced. No deployment, archive creation, or live financial
and identity mutations are part of this change.
