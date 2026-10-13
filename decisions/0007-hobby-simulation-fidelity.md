# 0007 — 1:1 hobby simulation fidelity, embedded official games, no commercial scope

Date: 2026-10-05. Status: decided.

## Decision

This platform is a **1:1 high-fidelity hobby simulation** created for personal usage and testing.
It embeds official games directly into the website for immediate play, and discards all documentation, requirements, and procurement tracks aimed at commercial gambling licensing (no CNPJ, no R$ 30M capital reserve, no SPA/MF licensing bureaucracy, no vendor RFQs).

## Implementation

1. **Embedded Official Games**: Top titles from Pragmatic Play (Gates of Olympus, Sweet Bonanza, Sugar Rush, Spaceman, Roleta Europeia, Blackjack), Spribe (Aviator), Hacksaw Gaming (RIP City), Play'n GO (Book of Dead), and Evolution (Lightning Roulette, Crazy Time) run directly inside the site via a responsive embedded theater player.
2. **Interactive Sportsbook**: Live public fixtures feed connected to an interactive Boletim de Apostas (Betslip) supporting single and combo bet simulation with demo balances.
3. **Double-Entry Wallet & Fast Cashier**: Integer minor units, thread-safe journal, and realistic Pix deposit and withdrawal simulations.
4. **Disposal of Commercial Documents**: All procurement RFQs (`p2/`, `p3/`), Brazilian gambling legal research (`research/`), and commercial decisions (0002, 0003, 0004) were removed from the repository.
