# 0015 — Jackpot follows real volume; Favoritos; game detail modal; chat widget

Date: 2026-10-06. Status: decided.

## Problem

Four visible blocks still behaved like television, not a product:

1. The jackpot ticker drifted by RNG every 2.5s without any money behind
   it.
2. There was no "Favoritos" list — opens and recents were tracked, but a
   player could not mark a favourite.
3. Clicking any game card launched it straight into the player, with no
   rules/info gate a real BR operator has.
4. No contact surface existed. Real sites all have chat/help on every
   view.

## Decision

1. **Real jackpot (`GET /api/jackpot`)**: the pool is a fixed seed
   (R$2.847.194,50) plus 1% of today's recorded stakes in the round
   ledger, so it grows only when real rounds land. The random-walk
   `setInterval` in CasinoHome is deleted; the panel polls every 15s and
   shows the ledger rule as its note.
2. **Favoritos**: star toggle in the game detail modal persists a
   `casa-favs` array in localStorage; a new Favoritos chip in the lobby
   filters by it (same category-switch re-read discipline as Recentes).
3. **Game detail modal**: clicking a card now opens a `.modal`/`.sheet`
   with provider, category, RTP (when the catalog ships one), a
   demo/volume-note, the jog button, and the favorite star. The card's
   own Jogar Agora button still 1-click plays.
4. **Live chat widget (`POST /api/chat`)**: canned-intent triage bot
   labelled "Central de Ajuda (simulada)". Replies are composed from
   real catalog counts and the real promo constants; nothing is
   persisted; greetings and fallback are explicit funnels
   (depósitos/saques/bônus/limites/jogos).

## Consequences

- Demo suite 64 -> 66 (JackpotChatTest: turnover moves the pool by 1%,
  stale rows ignored; chat triage + fallback verified).
- No placeholder editorial claims remain on the lobby: tournaments, news,
  jackpot, trends, and promo pages all recompute from the ledger.
