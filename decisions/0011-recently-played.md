# 0011 — Recentes: real recently-played persistence

Date: 2026-10-06. Status: decided.

## Problem

The "Recentes" chip filtered the catalog by `game_id`s found in the
player's server-side round history. Official provider demos — the bulk
of the catalog — run in an iframe and never write a server round, so a
player who only opened official games saw an empty tab, and for everyone
else the tab listed matches in arbitrary catalog order rather than
recently-played order.

## Decision

1. `web/app/page.jsx`: every `play(game)` appends `{game_id, ts}` to
   `localStorage["casa-recent"]` — de-duplicated, newest first, capped
   at 30. A write failure (private mode, disabled storage) degrades
   silently to server history only.
2. `web/app/components/CasinoHome.jsx`: the Recentes tab now unions the
   localStorage opens with server-history rounds, newest-first across
   both (localStorage wins ties by ts; in-house rounds keep their
   server-recorded chronology), and renders the tab sorted by that
   recency instead of catalog order. The stored list is re-read on every
   category switch, so a game opened moments earlier in the same session
   shows up when the user taps Recentes without a reload.

## Consequences

- No server change, no new postings: the ledger still records only real
  money events; the Recentes list is presentation state, per browser,
  unsynced — demo-appropriate.
- Sports rounds contribute no recent game (their rows carry no
  `game_id`), matching that the casino lobby lists casino games.
