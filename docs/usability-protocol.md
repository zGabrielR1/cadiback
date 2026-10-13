# P4 usability protocol — n=12 BR bettors, task success is the metric

## Method

Moderated, mobile-first, PT-BR, 30 minutes each. Vier tasks, no guidance:

1. Register to first Pix deposit (measures onboarding friction; target < 90s).
2. Place a 2-leg bet-builder bet (measures betslip taps; target <= 2 taps post-selection).
3. Explain what a cashout offer means and take half (measures comprehension).
4. Request a withdrawal and state when the money arrives (measures trust).

## Metrics (per flow, reported like pT: P(success | started))

- Task success, time on task, taps, error count, SUS score.
- A pattern enters `pattern-library.md` only with success >= 0.8 across the 12.

## Rules

- Sessions are independent: fresh build, fresh account, re-pulled copy each time.
- No leading scripts. Record verbatims; the library quotes players, not us.
- Failures are findings with dated fixes, never waivers. Two consecutive
  sub-0.8 flows freeze the front-end track until the fix session passes.
