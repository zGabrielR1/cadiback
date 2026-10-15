# ARCHITECTURE — operator

A 1:1 high-fidelity hobby simulation of a modern betting platform and casino for personal usage.
The frame outlives the model: `core/` never imports `verticals/` or `models/`;
verticals and pricing providers plug into one frame instead of forking it.

## Layout

```text
operator/
├── AGENTS.md / ARCHITECTURE.md / PROGRESS.md / CURRENTTASK
├── Makefile / scripts/verify.py / scripts/verify.sh
├── decisions/ / docs/
├── frame/            the money core + verticals (stdlib only)
├── demo/             playable product: HTTP server, slot, Pix, risk, sports seam
├── web/              Next.js storefront (React 19), builds to web/out
├── probes/           captured live-feed evidence & provider demos
└── frame/
    ├── core/money.py        integer minor units, largest-remainder allocation, payout math
    ├── core/ids.py          single identity: fixture keys, refusal-to-guess matching
    ├── core/ledger.py       append-only hash-chained JSONL, write-once / fill-once
    ├── core/devig.py        margin analysis + 4 fair-price methods (mult/power/additive/shin)
    ├── wallet/books.py      double-entry journal, idempotent postings, player views
    ├── validation/gates.py  freshness, odds sanity, margin bounds, duplicates, settlement
    ├── compliance/sigap.py  game registry, exclusions, limits
    ├── models/registry.py   fair-price provider registry (devig methods registered)
    ├── verticals/sports/    SportsEngine contract + deterministic stub
    ├── verticals/casino/    CasinoAggregator contract + deterministic stub
    ├── ops/scheduler.py     tiered loop, per-subject cooldown, daily cap, receipts
    ├── ops/notifier.py      ntfy fan-out (fail-open) + local file double for tests
    ├── ops/health.py        receipt freshness + ledger integrity + books balance
    └── tests/test_frame.py  45 execution checks; the executable spec

demo/
    ├── server.py            HTTP+JSON API, static serve (web/out → index.html)
    ├── arcade.py            crash, plinko, mines, dice, keno — sha256 draws, derived ladders
    ├── slot.py              6-tier paytable engine, SHA256 draw; one paytable per title (95.90 / 94.95 / 96.60)
    ├── casino.py            European single-zero roulette: deterministic ball, 35:1 straight, 1:1 even-money, RTP 97.30%
    ├── payments.py          CPF/CNPJ, Pix key, own-name bank, payout, allowlist
    ├── asaas.py             Asaas Pix rail: charge, QR, provider-confirmed credit (stdlib)
    ├── risk.py              velocity, stake spikes, loss-chase, RTP drift, dupes
    ├── sports_data.py       live-fixture seam (probes/) with stub fallback
    ├── vendor.py            official-content seam: https-only, gated titles
    ├── provider_demos.py    publisher-hosted demos: https + host allowlist
    ├── game_proxy.py        same-origin front for publisher games: wallet sync, /g/<game_id>
    ├── pg_proxy.py          PG Soft: a minted trial session, the hosts it
    │                        binds, and the measured money-API endpoints
    ├── index.html           zero-build fallback storefront
    └── test_demo.py         252 execution checks

web/                        React 19 + Next 16 App Router (static export)
    ├── app/page.jsx        shell: casino, sports, embedded official game player, cashier
    ├── app/components/SportsHome.jsx   leagues + events with live odds & betslip
    ├── app/components/CasinoHome.jsx   lobby: unified cards + official demos
    ├── app/globals.css     dark default + light toggle
    └── lib/api.js          shared fetch helper
```

## Three seams, one frame

| Seam | Module | Contract held fixed |
|------|--------|--------------------|
| Sports | `frame/verticals/sports/contract.py` `SportsEngine` | fixtures, markets, quote, accept, settle, void |
| Casino | `frame/verticals/casino/stub.py` `CasinoAggregator` | catalogue, launch, bet, wallet_credit, round_history |
| Payments | `demo/payments.py`, `demo/asaas.py` | Pix allowlist, own-name validation, two-step payout; a real Pix deposit credits only once Asaas confirms it |

The publisher-game proxy keeps one rule above the other two: **we never serve
bytes we cannot describe.** A body the proxy rewrites (document, money answer,
client bundle) is not revalidated against the publisher's validator, in either
direction; a body it passes through unchanged keeps the publisher's `ETag`
and answers 304. `GET /api/health` reports what the proxy did — a game that
does not load otherwise leaves no trace on the server — beside the PG mint
counters, so "the game did not open" is answerable as *the mint failed* or
*the proxy failed*, which are not visible in each other.

One publisher does not fit a suffix allowlist. PG Soft mints its hosts per
session (`m.<label>.com`, `api.<label>.com`) and signs every asset URL, so
the host binding is made by the process that asked for it: `pg_proxy.mint`
binds the exact strings the answer names, the session id travels in our own
path, and a host that is not `<prefix>.<label>.com` is never bound.

In-house originals (decision 0021): every launchable demo
game draws from `SHA256(game_id:round_id)` — slots through
their own paytable, roulette through the single-zero wheel
— and settles through `Books.place_bet` →
`settle_bet_win|loss` like any other bet. The live pulse
(`GET /api/live`) reads the plays log (15-minute window)
and the round ledger (newest wins, masked labels) only.

Concurrency and identity are part of the seam contract:
`Books` holds one `RLock` across the duplicate check, the balance guard, and the
append, so a request thread can never interleave a check with another thread's
posting. Payout destinations come from stored profile state.

## The lifecycle (money path)

`deposit` → `place_bet` → `settle` (win/loss) → `withdraw` (two-step: request then pay).

Every step posts a balanced journal entry under an idempotency key; every step is
gated (`validation/gates.py`); every close fills the integrity ledger exactly once.

## Wallet accounts

| Account | Meaning |
|---------|---------|
| `player:balance` | What the house owes the player (liability) |
| `player:bonus` | Bonus funds not yet released |
| `bonus:issued` | Contra for granted bonuses |
| `operator:cash` | House cash asset |
| `payable:player` | Approved withdrawals awaiting execution |
| `bet:staked` | Clearing: stakes awaiting settlement |
| `ggr:revenue` | Gross gaming revenue accumulator |
| `bonus:revenue` | Forfeited bonus accumulator |
| `adjustment:operator` | Manual corrections, always with a reason |

Invariant: the books sum to zero at all times. `assert_balanced()` enforces it.

## Execution substitutes

- `CURRENTTASK` is the objective; `PROGRESS.md` is the state.
- `decisions/` is the audit trail: newest file wins on conflict.
- `frame/tests/` is the spec: if it isn't tested by execution, it isn't true.
