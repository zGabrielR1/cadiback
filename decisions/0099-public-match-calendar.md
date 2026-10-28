# 0099 — Add upcoming matches to a calendar

## Behavior

Upcoming scheduled match details offer “Adicionar ao calendário” to guests and
members. The action exports a single local `.ics` file, with the supplied kickoff
converted to UTC, team names, competition/country and a public match-only link.
The full local date, time and timezone are visible beside the action.

Only scheduled matches with a valid future, timezone-qualified kickoff and valid
fixture identity are eligible. Live, final, postponed, cancelled, suspended,
abandoned and unknown statuses do not offer export. Failed feed refreshes retain
the previous match but disable export; recovery uses the current feed kickoff.
The action revalidates at click time and reports download preparation failures.

No end time, duration, attendance invitation or reminder is invented. This is a
one-time file rather than a subscription; both the file description and the
download status explain that schedule changes are not synchronized. Event UID
remains stable across time/name changes within the same host and fixture.

`web/lib/match-calendar.mjs` serializes the event using the
[iCalendar specification](https://www.rfc-editor.org/rfc/rfc5545), with CRLF lines,
escaped text, UTC timestamps and UTF-8-safe folding at 75 octets. The exporter
reuses `matchLink` to strip unrelated queries, private market filters and anchors,
and removes URL user credentials. No quote/bet/payment endpoint is needed.

## Validation

Unit cases exercise UTC offset conversion, public-only URLs, eligibility and
invalid dates, stable identity, line injection, long Unicode names and filenames.
`scripts/check_match_calendar.mjs` uses controlled APIs and checks guest/member
downloads at 1440/768/390/320, keyboard activation, local displayed kickoff,
current kickoff after refresh, failure/retry, selection/filter preservation,
unavailable status/date cases and light/dark overflow. Every API response is
stubbed, including the existing member settlement poll.

No deployment or live account/payment mutations are included.

Results: static build, verifier (zero problems), nine Node test files, core50,
backend426, calendar browser248 and market-finder browser408 pass. Narrow light
and tablet dark screenshots reviewed. Evidence: /tmp/operator-calendar-qa/.
