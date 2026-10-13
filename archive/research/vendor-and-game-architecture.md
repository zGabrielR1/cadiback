# Vendor & Game Architecture Specification

This document details the software architecture for game catalog aggregation, iframe embedding, wallet integration, and provably fair game mechanics.

## 1. Game Catalog Architecture

The platform supports a hybrid catalog structure combining:
1. **Official Provider Games**:
   - Live publisher-hosted demos from major studios: Pragmatic Play, Spribe, Hacksaw Gaming, Play'n GO, Evolution, and PG Soft.
   - Catalog defined in `probes/provider-demos.json` and validated by `demo/provider_demos.py`.
   - Security enforced via HTTPS protocol requirement and a strict host allowlist (`DEMO_HOSTS`).
2. **In-House Provably Fair Slots**:
   - Deterministic 3-reel slots (`Neon Gems`, `Fortune Ledger`) running directly on the backend engine.
   - Registered through `GameRegistry` with declared RTP (95.90%).

---

## 2. Iframe Container & Player Theater Mechanics

Official games are embedded directly into the site frontend:
- **Responsive Theater View**: 16:9 responsive viewport with full-screen capabilities.
- **Sandboxed Execution**: `allow="autoplay; fullscreen; screen-wake-lock; encrypted-media"`.
- **Wallet Isolation**: The third-party game executes on the publisher's secure servers, while player balance display and session state remain synchronized on the local platform.
- **Navigation Controls**: Reload trigger, fullscreen toggle, fallback external tab launcher, and a 1-click game-switcher strip.

---

## 3. In-House Slot RNG & Paytable Mechanics

For original platform titles (`demo/slot.py`):
1. **Draw Generation**:
   - Combines game ID, round ID, and cryptographic entropy using SHA-256:
     $$\text{hash} = \text{SHA256}(\text{seed} \parallel \text{game\_id} \parallel \text{round\_id})$$
   - Maps the hash into a uniform float $u \in [0, 1)$.
2. **Paytable Tiers**:
   - Tier 1: 3x SEVEN (100x multiplier)
   - Tier 2: 3x DIAMOND (15x multiplier)
   - Tier 3: 3x BAR (5x multiplier)
   - Tier 4: 3x LEMON (2x multiplier)
   - Tier 5: 3x CHERRY (1.2x multiplier)
   - Tier 6: No Match (0x multiplier)
3. **Double-Entry Wallet Settlement**:
   - Stake is debited from player cash (`player:balance` -> `bet:staked`).
   - If win: payout is credited from operator cash (`bet:staked` -> `player:balance` and `ggr:revenue`).
   - If loss: stake is swept to revenue (`bet:staked` -> `ggr:revenue`).
   - Books maintain a zero-sum invariant at all times.
