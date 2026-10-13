# Sportsbook Engine Specification

This specification defines the technical contract, lifecycle, and operational boundaries of the sportsbook engine seam (`frame/verticals/sports/`).

## 1. Engine Seam Contract (`SportsEngine`)

The engine protocol dictates six core lifecycle methods:

```python
class SportsEngine(Protocol):
    def fixtures(self) -> list[Fixture]: ...
    def markets(self, fixture_key: str) -> list[Market]: ...
    def quote(self, selection_key: str) -> Quote: ...
    def accept(self, bet_id: str, quote_version: str, player_id: str, stake_minor: int) -> BetReceipt: ...
    def settle(self, bet_id: str, result: BetResult) -> SettleReceipt: ...
    def void(self, bet_id: str, reason: str) -> VoidReceipt: ...
```

## 2. Bet Lifecycle & Double-Entry Accounting

1. **Selection & Quoting**:
   - Player selects an outcome from live markets.
   - Engine issues a versioned quote containing the decimal odds and maximum allowable stake.
2. **Acceptance (`place_bet`)**:
   - Atomic validation of player balance.
   - Leg 1: Debit `player:balance` by stake.
   - Leg 2: Credit `bet:staked` by stake.
   - An open bet ticket is recorded with unique `bet_id`.
3. **Settlement (`settle_bet`)**:
   - **Win**:
     - Leg 1: Debit `bet:staked` by stake.
     - Leg 2: Debit `operator:cash` by net profit (`payout - stake`).
     - Leg 3: Credit `player:balance` by total payout (`stake * odds`).
     - Leg 4: Credit `ggr:revenue` by `-net_profit` (negative GGR).
   - **Loss**:
     - Leg 1: Debit `bet:staked` by stake.
     - Leg 2: Credit `ggr:revenue` by stake (positive GGR).
   - **Void / Push**:
     - Stake returned in full from `bet:staked` to `player:balance`.

## 3. Betslip Frontend Integration

The storefront implements an interactive Betslip drawer (`web/app/components/SportsHome.jsx`):
- Dynamic potential payout computation.
- Quick stake buttons (+5, +10, +25, +50, +100).
- Immediate ticket placement with balance reflection.
