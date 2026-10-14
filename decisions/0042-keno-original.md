# 0042 — Keno Relâmpago: the game that was set aside for the wrong reason

**Date:** 2026-10-14
**Status:** accepted — `demo:keno`, BR-DEMO-0010, 97.00% RTP, verified live.

## 1. What was retrieved

The owner asked for "another interesting game you had an idea". Decision 0034
recorded exactly three candidates it had set aside, with the reason for each:

> Alternatives considered and set aside: **Keno** (a full paytable to get
> exactly right), **Wheel** (needs a spin visual and a weighted paytable),
> **Limbo** (overlaps Crash's target mode).

Three, not one. Keno is the one built here, because the reason it was set
aside turned out to be the interesting part.

## 2. The objection was a design flaw, not a fact

"A full paytable to get exactly right" is only a problem if the paytable is
**typed**. Typed means a human transcribed ten rows of multipliers and a typo
in any one of them silently changes the RTP — which is exactly the class of
bug this project exists to not have.

Keno does not need a typed paytable. It needs three facts, and the numbers
fall out of them:

1. **the hit probabilities are exact** — hypergeometric over 80 choose 20,
   `C(s,k)·C(80−s,20−k) / C(80,20)`, in `Fraction`, not a float;
2. **the shape is one decision, not ten** — every extra hit doubles;
3. **the scale is not a decision at all** — divide the whole ladder by its
   own expected return and multiply by `HOUSE_KEEP`.

So `keno_paytable` computes the ladder, and the RTP is 97.000000% at **every**
spot count by construction. There is no table to get wrong, and changing the
shape cannot make the house accidentally generous. The worst deviation across
all ten spot counts is **0.0000089%**.

```
1 spot    1h=  3.8800                                            RTP 97.00000%
5 spots   1h=0.6981  2h=1.3963  3h=2.7926  4h=5.5855  5h=11.1710  96.99923%
10 spots  1h=0.2240  2h=0.4480  3h=0.8960  4h=1.7919  5h=3.5839
          6h=7.1676  7h=14.3348  8h=28.6696  9h=57.3394 10h=114.6787  97.00053%
```

That is a real keno shape: a clean 2× ladder, low tiers under 1×, a top prize
of 114× on a ten-spot.

## 3. Two things that were nearly wrong

**Rounding the payout.** The first version floored `stake × multiplier` to
whole centavos, the same as `mines`. With ten tiers that costs up to a whole
centavo on *every paying round*, and the realised RTP at a R$1 stake came out
at **96.47%** — 1.5% of dust, far too much to still call the model 97%. The
fix is not a cleverer ladder, it is `keno_payout`: **round half up**, which is
unbiased, so the losses and gains cancel. Realised RTP is now 96.9–97.2%
across every spot count and stake, and `keno_realised_rtp` reports it rather
than the catalog pretending the dust is not there.

**The ladder's precision.** Snapping the multipliers to four decimals before
re-normalising is what keeps the model honest across the settling passes; at
two decimals the model error is 0.08% (fine, and it pays exactly at whole-real
stakes) but at four it is 0.0009% and the per-round rounding is the only dust
left. Both are defensible; four was chosen because the catalog advertises the
model number.

## 4. A sub-stake tier is not a win

1 hit on 10 spots pays **0.2240×**. That is money returned, not a win, and
`is_win` is `payout >= stake` — so the panel reports it in amber as
`retorno parcial` and never as a prize. This is the same honesty dice already
has (`under:99.00` pays 0.98×), and it is the reason keno settles through
`settle_casino` rather than the odds path.

## 5. What ships

- `demo/arcade.py`: `keno_hit_probability`, `keno_paytable`,
  `keno_multiplier`, `keno_rtp`, `keno_realised_rtp`, `keno_payout`,
  `parse_keno_selection`, `keno_draw`, `keno_round`. The draw is a
  digest-seeded shuffle of 1..80, the same discipline as mines, so a round is
  repeatable from the ledger alone.
- Selection: `"<spots>:<n1,n2,…>"`, e.g. `"5:3,17,42,58,71"`. The spot count is
  written out rather than inferred — the same three numbers under a different
  count is a different bet with a different ladder, so the two are kept apart.
- `demo/server.py`: `demo:keno` "Keno Relâmpago", BR-DEMO-0010, certified,
  category Originais.
- `web/app/components/KenoPanel.jsx`: an 80-number board (10×8), a spot
  selector 1–10, a quick-pick, and the live ladder with per-tier chance. Four
  cell states after a draw — hit, picked-but-missed, drawn-but-not-picked,
  idle — because those are three different things and they get three different
  colours. The ladder is mirrored in JS for display only; the server computes
  what is paid.
- Cover `games/demo-keno.svg`.

## 6. Verification

`KenoTest` (17): RTP is 97% at every spot count; the catalog carries the model;
each extra hit doubles; zero hits never pays; the hit probabilities sum to
exactly 1 and their mean is exactly `s·20/80`; a one-spot pays the odds of one
number; the realised RTP is reported and within 0.3%; the selection parses and
seven bad shapes are refused; the draw is deterministic, well-formed and
different per round; a round is repeatable; **every hit count pays exactly the
ladder**; a sub-stake tier is not a win; a round settles through the books;
a missing selection is refused and moves no money; a round lands in history
with its unit; the row is certified, categorised Originais and passes the cert
gate.

`frame` 45/45, `demo` 222/222 (+17), `verify.py` 0 problems. Live over HTTP:
catalog row present, eight 10-spot rounds settling through the books
(0×, 0.45×, 3.58×, 0.22× …), a missing selection refused with 400 and pt-BR,
and `books: 17 postings balance to zero`.

## 7. The other two, briefly

**Wheel** is still on the table and is the better next arcade original: its
only stated obstacle is a spin visual, which is vector work, and a wheel's
ladder is a single `(slots, multiplier)` table with a closed-form RTP — the
same derivation keno just proved. **Limbo** should stay set aside; it overlaps
Crash's auto-target mode and adds no mechanic.
