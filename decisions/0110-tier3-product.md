# 0110 — Tier 3 product surface (hobby-safe)

Implemented 2026-11-08, uncommitted. All money stays virtual; no real-money rails added.

## Odds drift + live ticker (#7, #10)
Pure helpers in `web/lib/odds-drift.mjs` (`priceSnapshot`, `snapshotPrices`,
`driftAlerts`, `biggestMovers`, `alertKey`) with node tests
(`web/lib/odds-drift.test.mjs`). `SportsHome` compares the previous feed
snapshot with each refresh: the top-3 board movers are shown in an in-app
ticker strip and price moves on **favorited** fixtures appear as a dismissible
in-app banner. No push, email, or any off-app notification.

## Responsible play (#8)
- Per-player daily limits (deposit / bets / session minutes) on the player
  row via `POST /api/player/limits`; enforced server-side in deposits and on
  spin/crash bet entry points; surfaced with today's totals in
  `profile.responsible` and the AccountView "Pausas e proteção" section.
- Session minutes caps verified session age in `player_session()`.
- Lifting a self-exclusion now records a 24h post-exclusion cooldown in
  `ExclusionRegistry` (persisted in the exclusions document); `assert_playable`
  refuses transactions while it runs.
- Regressions: `demo/test_responsible.py`.

## Promo polish (#9)
`profile.bonus` now reports `opt_out` and per-event `remaining_minor`;
`POST /api/player/promo-optout` toggles enrollment and `claim_bonus` refuses
while opted out. `PromosView` shows remaining rollover, an opt in/out control,
and keeps the existing turnover explanations — no auto-renewal anywhere.

## Cash-out preview (#10)
`BetslipTray` adds an explicitly labeled cash-out preview (92% convenience
estimate of the current combined odds). It is an estimate, not an offer;
server settlement remains authoritative. Crash already offers live manual
cash-out; no second cash-out surface was invented for sports.

## Verification
Node drift tests, backend responsible tests, and the full release gate must
pass before any claim of production readiness.
