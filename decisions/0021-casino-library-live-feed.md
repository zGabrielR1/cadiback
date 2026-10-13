# 0021 — In-house casino library + live activity feed

Date: 2026-10-09. Status: decided, implemented (suites reserved for next run).

## Problem

The operator looked like a casino but the only games playable
against our own books were two slots sharing one paytable
(95.90%). The "Mesa" and "Crash" categories had no launchable
in-house titles — only wallet-isolated publisher iframes — and
there was no real-time casino surface: the freshest activity
data was the 24h hot/cold board. A real casino's core product
is its own playable games and a live floor.

## Decision

**In-house game library (decision 0021):**

1. `demo/casino.py` — European single-zero roulette. The ball
   lands on a pocket from `SHA256(game_id:round_id)` (same
   draw discipline as the slots, so every round is repeatable
   and auditable from the round ledger). Real payouts:
   straight-up 35:1 (gross 36x), every even-money market 1:1
   (gross 2x). Zero is neither red/black, even/odd, nor
   low/high — it loses everything but a straight-up 0, which
   is what makes the house edge 1/37 (RTP 36/37 = 97.297%)
   on every market. A table game requires a selection:
   no selection is a clean 400, never a silent default.
2. `demo/slot.py` — per-game paytables. Neon Gems and Fortune
   Ledger keep the original table (every round on file was
   drawn against it); two new originals with distinct tables:
   Crimson Dragons (94.95%) and Gold Vault (96.60%).
3. `demo/server.py` — all three registered with BR demo
   certificates (`BR-DEMO-0003/0004/0005`, issued_for BR,
   SIGAP submitted) so the cert gate lets them launch;
   `Demo.spin()` routes roulette through the new engine
   (selection required) and slots through the per-game table;
   catalog rows now carry each game's real paytable.

**Live activity feed (`/api/live`, `Demo.live()`):**

Every figure from files the server already keeps — no
fabricated crowd:

- `active_players` / `active_games`: opens from the plays log
  inside a 15-minute window (who is on the floor right now);
- `latest_wins`: the 10 newest recorded wins from the round
  ledger, newest first, labels masked to "First L." like a
  casino floor ticker (never a full name);
- `jackpot_pool_minor`: the existing ledger-backed pool.

**Frontend:** `RoulettePanel.jsx` (selection grid 0–36 with
wheel colors + even-money chips), `SlotPanel` renders the
real per-game paytable from the catalog, `page.jsx` owns
selection/ball state and routes the panel, and `CasinoHome`
gains an "Ao Vivo Agora" strip polling `/api/live` every 15s.

## Consequences

- Launchable in-house originals: 5 (3 slots with distinct
  paytables + 1 table game), plus the deliberately uncertified
  Royale Roulette still blocked by the cert gate.
- Every roulette round settles through the double-entry books
  exactly like a slot round: `place_bet` → `settle_bet_win/loss`
  under the books lock, bonus-aware stake split, wager counted
  against any active promotion.
- Tests written (reserved for the next run): `CasinoTest`
  (determinism, all 37 pockets reachable, 36x/2x payouts,
  zero-loses-everything, RTP 36/37, selection required,
  book settlement both outcomes), `SlotPaytableTest` (tables
  sum to 1, distinct RTPs, catalog carries real paytables),
  `LiveTest` (window counting, newest-first masked wins,
  empty-lobby honesty). Expected suite: 80 → 98.
- Honest limits: no crash game yet (cash-out timing needs an
  interaction the spin flow cannot express); RTP figures are
  model RTPs of a deterministic draw, not lab-certified.

## Verification (this session)

- `import demo.server, demo.casino, demo.slot` clean;
  `rtp_of`: neon 0.959, crimson 0.9495, gold 0.966.
- Suites NOT run this session (reserved): `frame.selftest`
  was 43/43 and `demo.test_demo` was 80/80 before the
  change; the 18 new tests are written but unexecuted.
- Web export NOT rebuilt this session — rebuild with
  `cd web && npm.cmd ci && npm.cmd run build` before serving.
