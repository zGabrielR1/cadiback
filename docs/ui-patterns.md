# P4 pattern library — entries earned from sessions, not opinions

Nothing below is a decision until a usability session evidences it. Each pattern
carries its source: teardown note, vendor demo, or session id.

## Confirmed steals (teardown + vendor demos, session validation pending)

| Pattern | Source | What it does for us |
|---------|--------|---------------------|
| Market Info icon + settlement rules inline | Altenar | Kills the #1 support ticket class ("why did my bet lose") |
| Bet Mentor / Betting Insights | Altenar, Betano | Onboards novices without a tutorial; raises first-bet conversion |
| Sticky mobile footer + 2-tap betslip | Pragmatic Sports, Kambi/Shape | The clone gap: our betslip is two taps, priced visibly, void-explained |
| Featured events + ribbon + quick links CMS | Pragmatic Sports | Brasileirão-first merchandising without an app release |
| Streaming aligned to markets (100% fixture mapping) | Pragmatic Sports | Live bettors stay; misaligned streams cause void disputes |
| Transparent cashout (full/partial/auto with quoted price) | Kambi | Cashout distrust is the BR clone signature; we show the math |
| Pix-first cashier with withdrawal ETA | Market (Pix ~72%) | Deposit in seconds, withdrawal with a tracked two-step state |

## Anti-patterns (rejected with reason)

| Anti-pattern | Why it stays out |
|--------------|------------------|
| Bonus wall before first bet | Portaria 1231 ad rules + it tanks activation; bonuses live in EngageSuite, not in the funnel |
| EN-machine-translated PT-BR | Trust killer; every string ships from native copy |
| Credit-card-shaped deposit UI | Prohibited product (615/2024); the cashier never suggests it |
| Opaque void/cashout lines | Every void carries a reason; every cashout shows its quote version |

## Reference captures

| Capture | Where | What it gave |
|---------|-------|--------------|
| BR operator IA (Betano server-rendered; Superbet shell; Novibet/Bet365 403) | `docs/reference-ia.md` | header/menu, home-component order, bottom nav — mirrored in our own code |

## Session-evidence log

- _empty — first 12 sessions scheduled once clickable flows exist (see usability-protocol.md)_
