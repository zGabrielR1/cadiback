# Platform Assessment — 1:1 Hobby Project Fidelity

Status: 2026-10-05.
This repository is a **1:1 personal hobby simulation platform** created for personal testing and usage. It does not require real-world gambling licensing, CNPJ corporate registration, capital reserves, or regulatory compliance.

## Scoreboard

| Surface | Status | Implementation | Description |
|---------|--------|----------------|-------------|
| Money core | DONE | `frame/core/money.py` | Double-entry books, integer cents, replay safe |
| Ledger | DONE | `frame/core/ledger.py` | Append-only, tamper-evident hash chaining |
| Account & KYC | DONE | `demo/payments.py` | Realistic registration flow with CPF formatting |
| Deposits & Payouts | DONE | `demo/payments.py` | Instant Pix simulation with key verification |
| In-house Slots | DONE | `demo/slot.py` | Deterministic reel draws, paytables, RTP tracking |
| **Official Casino Games** | DONE | `probes/provider-demos.json` | Top official games (Pragmatic Play, Spribe Aviator, Hacksaw, Play'n GO, Evolution) embedded directly in the site iframe player |
| **Sports Betting** | DONE | `web/app/components/SportsHome.jsx` | Live fixtures feed with interactive Boletim de Apostas (Betslip) |
| Front-end Storefront | DONE | Next.js 16 + React 19 (`web/`) | 1:1 visual fidelity with leading betting platforms |
| Concurrency & Safety | DONE | `frame/wallet/books.py` | Thread-safe transactions and balanced books |
| Risk / Fraud Simulation | DONE | `demo/risk.py` | Real-time monitoring for spike, loss-chase, and velocity |

## Official Games Integration

The platform embeds official playable provider demos directly into the site:
- **Pragmatic Play**: Gates of Olympus, Sweet Bonanza, Sugar Rush, Big Bass Bonanza, Starlight Princess, The Dog House Megaways, Wolf Gold, Fruit Party, Big Bass Splash, Cleocatra, Wild West Gold, Spaceman, Roleta Europeia, Multihand Blackjack, Baccarat.
- **Spribe**: Aviator.
- **Hacksaw Gaming**: RIP City.
- **Play'n GO**: Rich Wilde and the Book of Dead.
- **Evolution**: Lightning Roulette, Crazy Time.

Each official game runs within a high-fidelity theater view with fullscreen controls, balance indicators, game reload, and a 1-click game switcher bar.

## Out of Scope (Deliberate)

- Real-money payment processor agreements (unnecessary for personal hobby project).
- Corporate licensing, R$ 30M authorization fees, and Ministry of Finance / SPA filings.
- Commercial CNPJ requirements.