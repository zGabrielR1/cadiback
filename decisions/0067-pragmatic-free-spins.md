# 0067 — Pragmatic free spins settle without a phantom stake

Date: 2026-10-19. Status: **shipped; unit-verified** (no live free-spins
trigger has been seen from the deploy).

Follows 0063 (the round tap this corrects), 0064/0065 (the same
payout-only rule for PG Soft's trailing feature wins).

## The gap this closes

0063 books a Pragmatic round from the movement of the publisher's own demo
saldo, and takes the split the answer names when it agrees with that movement:

    stake = c × l        (the triggering bet the client sent)
    payout = w           (the win)
    net    = ntp         (the publisher's own net)

That is exact for a paid spin, where `ntp = w − c×l`. It is wrong for a
**free spin**, where no stake is charged: the publisher's balance rises by the
win alone (`ntp = w`), and the answer still prints the triggering bet in
`c × l`. Reading `c × l` there books a bet the player never placed — the
payout-only branch of `settle_rgs_round` was never reached, so the round was
recorded with a stake.

## Decision: the publisher's net is authoritative

`spin_round` now prefers `ntp` when it is present, because it is the field that
agrees with the saldo movement by definition:

    stake = payout − ntp

A paid spin is unchanged (`w = 50.00, ntp = 48.00, c×l = 2.00` → `200/5000`).
A free spin falls out of the same formula (`w = 50.00, ntp = 50.00` →
`0/5000`); the nominal `c × l` is ignored because it is the one number that
did not move. `c × l` remains the fallback for an answer that carries no `ntp`.

The tap marks the entry `free_spins: true` when a round is paid with no stake,
so the admin ring buffer says which shape it saw. Settlement is otherwise
unchanged: `settle_rgs_round` with `stake = 0` already pays through
`Books.settle_casino_payout`, the rule PG Soft's trailing feature win
introduced in 0065.

## Why not detect free spins directly

The answer has no documented `free_spin` flag in the captures 0062/0063
produced, and the tap deliberately reads the publisher's accounting rather
than guessing from symbols or feature counters. `ntp` is that accounting: a
round where the balance moved by exactly the win *is* a round with no stake,
whatever the client chose to print alongside it.

## Tests

`PragmaticRoundTapTest` (11) now covers:

* the parser prefers `ntp` and reads a free spin as `(0, win)`;
* a free-spin movement posts `stake 0 / payout 5000` to the wallet, through
  the payout-only write, and keeps the net exact;
* the phantom stake is **not** learned — the next paid spin learns its own
  `200` from its loss;
* the paid-spin cases (named split, movement fallback, replay dedupe, cap
  refusal) are unchanged.

## Limits

* **A free spin whose answer carries no `ntp`** still falls back to `c × l`
  and would be booked with a phantom stake. Measured against the captured
  `doSpin` shape, which always carries `ntp`; a title that omits it would need
  its own capture before the fallback can be trusted.
* **A free spin with no win** does not move the saldo, so it is not booked at
  all (net zero is also what a replay looks like). No money is lost; only the
  round count is.
* **No live free-spins trigger has been seen from the deploy.** The feature is
  usually awarded by a scatter, and the captures so far are base-game spins.
  The unit tests stand in until a real trigger is driven.
