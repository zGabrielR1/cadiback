# Sports Data Gathering & Odds Analysis Specification

This document specifies the technical architecture for the platform's sports data pipeline, odds processing, and mathematical fair-price (devig) analysis.

## 1. Sports Data Gathering Pipeline

The platform uses a modular sports data seam defined in `demo/sports_data.py` and `scripts/fetch_live_fixtures.py`:

1. **Feed Ingestion**:
   - Scrapes public fixtures and scoreboard endpoints (e.g. ESPN `site.api`, covering Serie A, Brasileirão, NFL).
   - Extracts fixture metadata: unique fixture key (`{home_slug}-{away_slug}-{kickoff_date}`), competition, teams, status, and kickoff timestamp.
2. **Markets & Odds Normalization**:
   - Maps market types (`1x2`, `2way`, `spread`, `totals`).
   - Converts moneyline formats (e.g. American `+235` / `-150`) to standard European decimal odds (`3.35` / `1.67`).
   - Validates odds bounds: minimum odd 1.01, maximum odd 1000.00.
3. **Storage & Caching**:
   - Captured evidence stored in `probes/live-fixtures.json`.
   - Deterministic stub fallback via `frame/verticals/sports/stub.py`.

---

## 2. Odds Analysis & Devig Models

Bookmakers price markets with an embedded margin (overround). To extract the **true underlying probability** of sporting outcomes, the platform implements four analytical devigging models in `frame/core/devig.py`:

### Overround (Bookmaker Margin)
For decimal prices $O_1, O_2, \dots, O_n$, the implied probabilities are:
$$p_i = \frac{1}{O_i}$$
The overround $M$ is:
$$M = \sum_{i=1}^n p_i - 1$$
* A fair market has $M = 0$.
* A commercial bookmaker typically prices markets with $M \in [0.03, 0.10]$ (3% to 10% margin).

### Devigging Methods

1. **Multiplicative Devig (Proportional)**:
   Normalizes implied probabilities proportionally:
   $$P_{\text{fair}, i} = \frac{p_i}{\sum_{j} p_j}$$
   Simple, but tends to under-correct the favorite-longshot bias.

2. **Shin Method (Informed Bettor Model)**:
   Models the market as a mix of uninformed noise bettors and a fraction $z$ of informed bettors with inside information.
   - Solves for the insider trading parameter $z \in [0, 1]$ such that the true probabilities sum to 1.
   - Monotonic and bounded, proven to accurately capture the favorite-longshot bias observed in live sports markets.

3. **Power Devig**:
   Solves for exponent $k > 0$ such that $\sum p_i^k = 1$.
   Adjusts longshot probabilities downwards while preserving market ordering.

4. **Additive Devig**:
   Distributes the margin evenly across all selections:
   $$P_{\text{fair}, i} = p_i - \frac{M}{n}$$

---

## 3. Real-Time Analysis Output

The admin panel and analysis engine expose:
- **Implied vs Fair Probabilities**: Side-by-side comparison for each market runner.
- **Fair Decimal Odds**: $O_{\text{fair}} = 1 / P_{\text{fair}}$.
- **House Edge / Vigorish %**: Exact percentage margin charged on each selection.
- **Value Betting Signals**: Highlights discrepancy between bookmaker offering and fair pricing.
