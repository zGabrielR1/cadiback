# 0019 — Casino catalog grows 22 → 40 publisher-hosted demos

Date: 2026-10-08. Status: decided.

## Problem

The casino section's official shelf was thin: 22 demos, one
mini-game (Aviator), four Play'n GO titles total one. The shelf looked
like a sample, not a lobby.

## Decision

Add 18 rows to `probes/provider-demos.json`, every URL live-verified
2026-10-08 before listing:

1. Pragmatic Play ×7 (gameSymbol proven by the launcher serving the
   named client; `vswaysbuffalo` rejected with the casino-support
   error page and left out): Gates of Olympus 1000, Sweet Bonanza
   1000, Sugar Rush 1000, Big Bass Bonanza 1000, Zeus vs Hades —
   Gods of War, Joker's Jewels, Bonanza Gold.
2. Spribe ×7 (unknown launch slugs answer `404 Game not found`;
   `hilo` rejected; valid slugs only): Mines, Plinko, Dice, Keno,
   Goal, Mini Roulette (Mesa shelf), Hotline.
3. Play'n GO ×4 (unknown gids answer HTTP 400): Reactoonz,
   Fire Joker, Moon Princess, Legacy of Dead.

Deliberately NOT added: PG Soft numeric ids (m.pgsoft-games.com is
unreachable from here — DNS fails even for the two ids already
listed, so new ids could not be verified), Hacksaw product-id builds
(guessing versioned paths risks dead embeds), Evolution (site
marketing pages, not playable demos).

## Consequences

- Catalog counts: pragmatic_play 21, spribe 8, play_n_go 5,
  pg_soft 2, evolution 2, hacksaw 1 — 40 wallet-isolated rows.
- Covers: generated per-game SVG placeholders (`web/public/games/`);
  the card already falls back cover → slug.svg → icon, so no UI
  change. Frontend rebuilt (new public assets made the export
  stale); `web/node_modules` pruned post-build per convention.

## Verification

- `provider_demos.load()`: 40 accepted, 0 dropped. Live smoke on
  `/api/catalog`: 40 rows. `demo.test_demo` 80/80, `frame.selftest`
  43/43, `verify.py` 0 problems.
