# 0050 — Username accounts + a live sports feed (Livescore)

Date: 2026-10-16
Status: accepted

## Context

Two independent gaps shipped together, both about what the storefront shows
back to a player:

1. **Accounts had no handle.** Signup took name + email + CPF + password, and
   login took email-or-CPF. The owner asked for a username chosen at signup and
   usable to log in — the ordinary shape for a betting site, and the one thing
   the account row was missing.
2. **The deployed sports feed was dead.** `https://cadiback.onrender.com/api/sports`
   returned `source: "inhouse"` — the deterministic floor — instead of real
   fixtures. The cause was two-fold and only visible together: `.dockerignore`
   line `probes/*cache*.json` keeps the ESPN snapshot out of the Render image,
   *and* ESPN's scoreboard (`site.api.espn.com`, `site.web.api.espn.com`)
   answers **403 from datacenter egress** (verified: 403 through the cloud
   fetch, 200 from this laptop). With no cache and no reachable feed,
   `EspnSportsEngine` threw and the chain fell through to the slate. The second
   real source, Superbet's v3 offer server, "doesn't work anymore" (owner) —
   the endpoint is gone.

## Decision

### 1. Username: required at signup, a login identity, case-insensitive

- `demo/payments.py:validate_username` — `^[a-z0-9][a-z0-9._-]{2,19}$`, 3–20
  chars, **normalised to lowercase** so `Ana` and `ana` are one account. The
  store keeps only the lowercase spelling.
- `Demo.register_player` **requires** a username and refuses a duplicate
  (the same "already taken, log in" hint the email/CPF rules give).
  `Demo.upsert_player` takes it as optional so the legacy/CPF-keyed path never
  wipes a handle.
- `Demo.login_player` resolves the identifier through a new `Demo._find_player`:
  **username first**, then email **only when the identifier holds an `@`**, then
  the CPF whose id derives the deterministic `player-…` key. Unknown and
  wrong-password stay the same message after the same delay.
- Persistence: `Player.username` in `demo/models.py` and a **new** migration
  `supabase/migrations/20261016000000_players_username.sql` (applied *after*
  0049's schema, never editing it): `username TEXT NOT NULL DEFAULT ''` plus a
  **partial** unique index on `lower(username) WHERE username <> ''`, so the
  empty default of a legacy row never collides.
- Storefront: `lib/validation.js:validateUsername`, a signup field in
  `AccountModal.jsx`, the login identifier branch in `page.jsx` (email vs
  all-digits CPF vs handle), `AccountView.jsx` shows it, and the painel's
  test-account form + table gained the column.

### 2. Sports feed: Livescore is the real source; Superbet is removed

`frame/verticals/sports/livescore_engine.py` implements the same `SportsEngine`
contract over **Livescore's public match API**
(`prod-public-api.livescore.com/v1/api/app/date/soccer/<YYYYMMDD>/0`, no key),
chosen because it is the one candidate verified **200 from both this machine and
the cloud fetch** while carrying the day's fixtures across every competition it
covers **with an in-play status and running score** (`Eps` → our statuses: `NS`
scheduled, `FT`/`AET`/`Pen.` final, the postponement family, everything else —
`HT`, `24'` — in play). It fetches today+tomorrow, orders live → upcoming →
finished, caps at 240 fixtures, caches to `probes/livescore-cache.json` with the
usual fail-open-to-cache / fail-closed behaviour, and never serves Livescore's
own prices — every quote is the in-house deterministic book.

- `Fixture` gains an optional `status`; a source that ships in-play state fills
  it, a source that only ships a kickoff leaves it empty and `Demo.sports_showcase`
  derives it from the clock as before.
- `superbet_engine.py` + `probes/superbet-cache.json` are **deleted**; nothing
  references them (tests, `frame`'s connection-leak check, `verify.py`).
- `Demo.sports_showcase` order is **Livescore → ESPN → deterministic slate**.
  ESPN stays as the second source because it adds multi-sport coverage locally;
  it simply fails fast (403) where the cloud cannot reach it. Crucially the
  showcase now **records each failed source** (`errors: [{source, error}]`) and
  still returns it when a later source carries the board — a dead feed is
  visible in the payload, not silently swallowed.

The cache is deliberately *not* shipped in the image: with a cloud-reachable
source the first refresh populates it, and `.dockerignore` keeps machine state
out of the build (the root cause was a missing cache, not the exclusion itself).

## Alternatives considered

1. **TheSportsDB** (the first pick): key-free and multi-league, but its
   `eventsday` endpoint stopped answering from both this machine and the cloud
   (`TimeoutError`, 0 bytes) during this work, and its free key's
   `livescore.php` is 503 — no in-play data. Not dependable enough to be the
   primary source.
2. **OpenLigaDB** (`api.openligadb.de`, 200 from both): real and stable, but
   German leagues only — too thin for the board.
3. **FIFA `api.fifa.com`** (200 from both): returns historical tournament
   fixtures, no current-day schedule. Rejected.
4. **Ship the ESPN cache in the image** (drop the `.dockerignore` line): fixes
   the cold start but not the 403 — the deployed feed would serve a stale
   snapshot forever. Rejected: the source must be reachable, not cached.
5. **Username optional / derived from email**: the ask was a chosen handle;
   deriving it silently would make "log in with your username" fragile. Rejected.

## Notes

- Migration applied through the dashboard SQL editor (the direct `db.<ref>` host
  does not resolve from IPv4-only egress — see `docs/supabase.md`).
- Suites: `frame` 45/45, `demo` 280/280 (+5 username, +1 Livescore contract,
  −1 Superbet), `verify.py` 0; export rebuilt.
- Deployed to Render (`cadiback`) and Vercel (`cadiback-web`); live-verified.
