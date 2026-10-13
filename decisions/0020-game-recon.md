# 0020 — game-recon: client-side analysis of the embedded demo catalog

Date: 2026-10-08. Status: decided.

## Problem

The site embeds 40 publisher demos, but nobody had mapped how any of
them are delivered: what the launcher loads, where round outcomes
come from, which URLs are even playable. Blind embeds are a fidelity
and honesty risk (see the Big Bass Splash mislabel below).

## Decision

New project `research/game-recon/` (own README, `targets.json`
generated from the catalog, reusable `scripts/recon_game.mjs`
headless-Chromium pass). All 40 targets reconned this session.
Recon stores metadata only (`meta.json` tech signals +
`network.json` request inventories) — no response bodies, no game
bytes on disk, extending the no-rehost rule (0006/0008).

Findings (`research/game-recon/findings.md`): uniform PP launcher
shape (canvas + HTTP `.do` game server), Spribe Angular SPA +
SmartFoxServer `BlueBox` backend (v2.1.50-hotfix), PGO dual
websockets, Hacksaw atlas/KTX2 pipeline, Evolution = marketing
pages, PG Soft DNS-blocked from here. Playable local clones are
BLOCKED by design (server-side outcomes + publisher assets), so
the reconstruction deliverable is documentation, never a clone.

Two catalog corrections applied from the captures: `pp:big-bass-
splash` (`vs10bbextreme`) actually serves **Big Bass Amazon
Xtreme** — title fixed; 5 PP launchers (wild-west, spaceman,
roulette, blackjack, baccarat) boot-stall headless (PARTIAL,
needs a real-Chrome follow-up, not a catalog change since their
URLs answer HTTP 200).

## Verification

- `out/` holds 40/40 game dirs. Gates: `demo` 80/80, `frame`
  43/43, `verify.py` 0 problems, live catalog smoke still 40 rows.
