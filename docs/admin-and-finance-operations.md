# Admin & Finance Operations Specification

This specification governs platform administration, user management, financial ledger oversight, and risk monitoring.

## 1. Financial Operations & Balance Sheet Invariants

The platform's financial core is grounded in double-entry bookkeeping (`frame/wallet/books.py`):

1. **Fundamental Equation**:
   $$\text{Assets} - \text{Liabilities} - \text{Equity / Reserves} = 0$$
   Every posting must contain balanced legs that sum exactly to zero.
2. **Key Accounts**:
   - `operator:cash`: Liquid cash reserves of the house.
   - `player:balance`: Total liability owed to active players.
   - `payable:player`: Approved withdrawals pending settlement.
   - `bet:staked`: Clearing account holding active wagers.
   - `ggr:revenue`: Cumulative Gross Gaming Revenue.
   - `adjustment:operator`: Manual administrative balance interventions.

## 2. User Management & KYC Simulation

1. **Player Lifecycle**:
   - Registration with CPF formatting and validation.
   - Pix key classification (CPF, email, phone, EVP).
   - Bank account details verification.
2. **Administrative Controls**:
   - Balance Adjustments (Credit/Debit with mandatory recorded audit reason).
   - Temporary or permanent exclusion enforcement (`frame/compliance/sigap.py`).
   - Transaction and round history inspection.

## 3. Fraud & Risk Monitoring

The real-time risk engine (`demo/risk.py`) screens all player activity for:
- **Velocity**: Excessive spin or bet rate over short timeframes.
- **Stake Spikes**: Abrupt multipliers above baseline wager size.
- **Loss Chase**: Rapid stake increases immediately following consecutive losses.
- **RTP Deviation**: Statistical variance drifting significantly from game RTP.
