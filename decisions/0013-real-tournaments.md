# 0013 — Tournaments panel shows real leaderboards, not theatre

Date: 2026-10-06. Status: decided.

## Problem

"Torneios em Andamento" rendered two hardcoded cards ("R$ 50.000 (Demo)",
"R$ 25.000 (Demo)") — a published competition structure with no competition
behind it, the same honesty violation the promo page had before decision
0009.

## Decision

The section now reads `GET /api/tournaments` (`Demo.tournaments`), computed
from the append-only round ledger for the current UTC day:

1. **Maior Ganho (hoje)** — per-wallet max single `payout_minor` from
   today's round rows; top 3.
2. **Mais Rodadas (hoje)** — per-wallet count of today's round rows; top 3.
3. Player labels come from the players store (real names); rows with a
   blank player or a stale `ts` are ignored. Empty days render an explicit
   "Nenhuma rodada hoje" state, and the payload carries a note that no
   organized tournaments exist — the theatre is gone.

## Consequences

- Demo suite 60 -> 62 (TournamentTest: today-only counting, win ordering,
  empty-day shape, note present).
- The panel re-reads `/api/tournaments` every 60s; it reflects outcomes
  from `/api/spin` and `/api/bet` with no caching layer.
- A future real tournament feature would subclass this board, not
  resurrect the fake cards.
