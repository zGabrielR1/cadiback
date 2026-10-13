# 0014 — Notícias derived from server facts, not static copy

Date: 2026-10-06. Status: decided.

## Problem

`Notícias da Plataforma` rendered a hardcoded `NEWS` array — "Mais de 20
jogos oficiais adicionados ao catálogo" etc. — text the code never
verified. Same honesty class as the promo page (pre-0009) and the
tournament cards (pre-0013).

## Decision

`GET /api/news` (`Demo.news`) builds every card from state the server
already holds:

1. **CASSINO** — official demo count / provider count, from the real
   `provider_demos.json` load (22 jogos, 6 provedores today).
2. **ESPORTE** — the actual `fetched_at` of `probes/live-fixtures.json`.
3. **ALTA** — the number-one game on `Demo.trending()` for the last 24h,
   title joined server-side from the catalog.
4. **PRÊMIO** — today's biggest win from `Demo.tournaments()`, formatted
   as `R$ 1.234,56`.
5. **PROMOÇÕES** — factual pointer to the working promo mechanics
   (decision 0009).

The CasinoHome panel fetches it on mount and every 60s, with loading and
empty states, same as the tournament and trending panels. Demo suite
62 -> 64 (NewsTest: catalog/provider/fixture facts always present; ALTA
and PRÊMIO surface after a recorded open + a recorded win row).
