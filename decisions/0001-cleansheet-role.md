# 0001 — cleanSheet is a shadow risk monitor, never customer pricing

Date: 2026-10-01. Status: decided. Newest file wins on conflict.

## Decision

cleanSheet (`research/cleanSheet/`) runs beside the operation, never inside the
customer pricing path. Its permitted uses:

1. Sharp-bettor CLV: which players beat our closes, on which leagues and markets.
2. Latency/repricing priors: Superbet-recon method applied to our own repricing speed.
3. Exposure limits: per-league, per-market liability ceilings informed by microstructure.
4. Later: a provable best-price marketing claim, only with n>=500 archive + CORP green.

## Why

- The model is measured 2-8x less calibrated than the market (rolling-50 biases
  +4.1 to -16.3pp vs ~2pp market; 17,368-close audit). Pricing customers with it
  means pricing worse than the competitors we buy from.
- As the house, edge is vig discipline + handle + retention, not prediction.
  cleanSheet was built to beat a close as a bettor; that objective does not transfer.
- The 5pp/3% gate is unreachable by measurement, not by absence of evidence.
  Wiring it into pricing would manufacture bets from noise.

## Consequences

- No `find_edge.py` output may settle, price, limit, or message a player.
- The frame's `models/registry.py` holds fair-price providers for margin analysis
  only; margin analysis informs the house, it never sets a customer price.
- Promotion of any cleanSheet signal into operations needs its own prereg +
  paired test + this decision superseded in writing.
