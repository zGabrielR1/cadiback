# 0012 — Quentes e frios: activity board from real opens + rounds

Date: 2026-10-06. Status: decided.

## Problem

The lobby had no trend board, and the honest inputs were missing: official
iframe games never wrote a server round, so a board built only from
`rounds.jsonl` would be a board of the three in-house titles.

## Decision

1. `Demo.record_play` + `POST /api/play`: every `play()` in the web app
   posts one open (`game_id`, optional player, UTC ts) to
   `demo/data/plays.jsonl`. Presentation state, never a books posting —
   an open moves no money, so the wallet ledger stays strictly
   money-events-only.
2. `Demo.trending` + `GET /api/trending`: the last 24h of opens + round
   records per `game_id` (ISO ts window, torn-line tolerant, only known
   catalog ids counted). `hot` = top 8 by opens+rounds desc; `cold` = up
   to 8 catalog titles with zero activity. Poll-friendly, no caching —
   the JSONL read is a hobby-scale file.
3. CasinoHome renders a "Quentes e Frios" panel: hot games as playable
   cards with their 24h opens/rounds counts, cold titles as a dim row.
   The panel refreshes every 60s.
4. Definition locked by the user: hot/cold = activity (opens + rounds in
   the last 24h), covering official games too — not payout-based, which
   would only be meaningful for the in-house titles.

## Consequences

- Demo suite 56 -> 60 (TrendingTest: opens count, rounds count, torn /
  unknown / stale rows never leak, 24h window boundary, missing id 400).
- A "most played today" statement on the site is now backed by a file,
  not a random ticker.
