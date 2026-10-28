# 0097 — Search and filter the markets within a match

## Problem

Public match detail rendered every valid market as one long list. Finding a
particular total, player or selection required scanning the whole list, and
signed-in players could not isolate the market containing their slip selection.

## Behavior

- Add match-local search and category controls with counts for result, totals,
  discipline, corners, players and other supplied market kinds. Only categories
  with data are offered, except an active category remains visible at zero when
  a refresh removes its markets. Unknown market kinds remain available in Other.
- Search combines market labels, outcome names, source and line. It normalizes
  accents and decimal commas (for example gols 2,5). Labels use the sport's total
  units and period wording. The global fixture search stays separate.
- Signed-in players can show only markets containing their exact current fixture,
  market, line and outcome identities. Filters never change slip selections or
  accept new prices. Clearing/recovering filters returns focus to market search.
  Guests retain read-only prices and no private selection controls.
- Empty results offer recovery while retaining match statistics and provenance.
  Filters persist through feed changes and retry; counts reflect valid feed
  markets rather than malformed or invented entries.
- Suspended, postponed, cancelled and abandoned matches expose read-only prices,
  consistent with the existing slip's unavailability rules. Ended matches retain
  their existing read-only behavior.
- Authenticated tablet checks exposed inherited overflow: the supporting panels
  used a two-column grid inside a narrow sidebar. At 761–900px the market column
  now occupies a full row, with supporting panels below it. Grid children can
  shrink and long supporting text can wrap.

## Validation

Unit checks cover category coverage including unknown kinds, combined search,
accent/decimal normalization, source filtering, exact selection identity, and
sport-specific labels. scripts/check_market_finder.mjs covers guests/members at
1440/768/390/320 with controlled API/session responses, changing feeds, unavailable
match states, empty recovery, keyboard/focus behavior and both themes. No real
quote, bet, payment or identity mutations are performed.

Serve web/out at 127.0.0.1:8784 or set OPERATOR_QA_URL. Supply Playwright through
module resolution or PLAYWRIGHT_MODULE; CHROME_PATH optionally selects a browser.
Screenshots are written to /tmp/operator-market-finder-qa. Existing match-link
regressions and required project checks are also run. No deployment or archive
creation is included.
