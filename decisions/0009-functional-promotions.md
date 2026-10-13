# 0009 — Functional promotions: real bonus mechanics through the wallet

Date: 2026-10-05. Status: decided (amends 0007 scope: promos page honesty).

## Problem

The Promoções page advertised a welcome bonus (100% up to R$500) and a
daily 10% cashback with no mechanics behind either — a published offer
with no fund, which the project's own honesty standard (p11) treats as a
claim, not a feature. The frame wallet already supported `grant_bonus`,
bonus-aware `place_bet`, and a `player:bonus` account; the product never
exercised any of it.

## Decision

Promotions become real mechanics, small numbers, demo scope:

1. **Welcome bonus** — 100% of the first deposit, capped at R$500,
   first deposit must be at least R$20. One claim per wallet
   (`demo:bonus:{player}:welcome`). Wagering target: 20x the granted
   bonus.
2. **Cashback** — 10% of the day's (UTC) net loss from settled rounds,
   capped at R$200, minimum claim R$1, one claim per day
   (`demo:bonus:{player}:cashback:{day}`). Wagering target: 1x.
3. **Wallet truth** — every claim posts `bonus_grant`
   (`player:bonus` / `bonus:issued`); the promo store
   (`demo/data/promos.json`) records only claim state and wagering
   progress, never money.
4. **Cash-first stakes** — a stake is funded from `player:balance`
   first; bonus is staked only when cash runs out. The split is computed
   under the books lock (TOCTOU discipline from audit 2026-10-01).
5. **Bonus wins stay bonus** — frame change: `settle_bet_win` gained
   `bonus_part`; the bonus-funded portion of a payout returns to
   `player:bonus`, never to withdrawable cash. Cash portion unchanged.
6. **Conversion** — when the active event's wagering target is met, the
   entire `player:bonus` balance converts to `player:balance` in one
   posting (`bonus_convert`). Bonus credited after conversion (a pending
   bonus-staked win settling late) converts on the next settle/spin/bet:
   orphaned bonus is released, never held hostage.
7. **One active event at a time** — a claim is refused while an
   unconverted bonus with funds exists. An event whose funds were fully
   staked before the target is dead and closes itself so it cannot block
   claims forever.
8. **Bonus is not withdrawable** — withdrawals read `player:balance`
   only, so `player:bonus` can never leave as cash before conversion.

## Consequences

- `POST /api/bonus` (kinds `welcome`, `cashback`), profile exposes
  `bonus_minor` + a `bonus` view (eligibility, progress, percent).
- The Promoções page shows claim buttons and a live wagering progress
  bar; the header shows `saldo + bônus`.
- Frame suite 42 -> 43 checks (bonus-win routing proven by execution);
  demo suite 50 -> 56.
