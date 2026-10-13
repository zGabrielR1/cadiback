# 0010 — Live sports view polls the fixture feed every 15s

Date: 2026-10-06. Status: decided.

## Problem

The sports view fetched `/api/sports` once per visit. The server already
simulates a live bookmaker for fixtures whose status is `IN_PROGRESS`/`LIVE`
(deterministic sha256 re-pricing on a 30s bucket, `demo/server.py:
sports_showcase`), and `scripts/fetch_live_fixtures.py` can refresh the
capture — but the UI never re-asked, so prices only moved on a full reload
(or never, if the user stayed in the sports view).

## Decision

1. `web/app/page.jsx`: while the `sport` view is mounted, poll
   `/api/sports` every 15s and replace the sports state (initial load
   still happens on entering the view; betslip selections keep their
   locked price — standard practice).
2. `web/app/components/CasinoHome.jsx`: the landing pricing strip
   ("Super Odds"/prov) polls the same endpoint every 15s instead of
   fetching once on mount.
3. No server change. Provenance is unchanged: the polled payload keeps
   `source`, `provenance`, `licensed_feed`, and the not-licensed-rights
   note; with zero live fixtures in the current capture the prices are
   constant — polling surfaces new fixtures/statuses/prices from the next
   capture within one tick rather than inventing motion.

## Consequences

- 15s worst-case lag of 2x the 30s bucket: acceptable for a demo feed.
- When a fixture flips to live (or a new capture lands), the sports view
  starts ticking with no reload; the sports status badges (`LIVE`) follow
  the feed automatically.
- `web/node_modules` had vanished (overnight cleanup); `npm ci` restored
  it, export rebuilt, fresh chunk verified served by `demo/server.py`.
