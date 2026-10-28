---
target: web/app/page.jsx (Original homepage)
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 4
target_identity: "file:/home/pwdmcl/data/ppp/ppp/pentesting/betting/operator/web/app/page.jsx"
target_fingerprint: "sha256:8f2c7b91dbf2a1d457fa8d3dc20618d02e2cb4f3aea3b911fc7025b18a871e52"
target_path: /home/pwdmcl/data/ppp/ppp/pentesting/betting/operator/web/app/page.jsx
timestamp: 2026-10-24T04-55-22Z
slug: web-app-page-jsx
---
# Impeccable critique — production Original (Candibet homepage)

Target: `web/app/page.jsx` (Original/classic homepage) · rendered at `http://127.0.0.1:8765/`
Mode: **Operate** · Method: dual-agent (A: design-review sub-agent · B: detector/browser sub-agent)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Source + updated-at line is hidden under 1101px, so phone/tablet users cannot judge price staleness. |
| 2 | Match System / Real World | 3 | "Em alta" labels the first three non-final fixtures by kickoff; no popularity data exists. |
| 3 | User Control and Freedom | 2 | Desktop betslip cannot be collapsed (toggle hidden ≥1281px); only exit is `×`, which deletes every selection. No fixture URL or skip link. |
| 4 | Consistency and Standards | 2 | Light theme: row odds background equals row background and the border is invisible white alpha. Active Favoritos chip uses error red. Same price is lime in featured cards, ink in rows. |
| 5 | Error Prevention | 2 | Withdrawal and self-exclusion execute on one click; self-exclusion is hard-coded to 2027-01-01. |
| 6 | Recognition Rather Than Recall | 2 | Changing `Mercado` rewrites every row with no per-row tell. 3-up cards make 1/X/2 comparison a zig-zag. Zero-result search never echoes the query. |
| 7 | Flexibility and Efficiency | 2 | 154 rows × 7 controls ≈ 1,100 tab stops; no pagination, league jump, sort, `/` shortcut, or roving tabindex. |
| 8 | Aesthetic and Minimalist Design | 3 | Dark theme is excellent; the filter story is told three times (toolbar, "mostrar só ao vivo", rail "Ao vivo"). |
| 9 | Error Recovery | 2 | Field errors are specific, but a 0-result search dead-ends and failed login leaves focus on submit. |
| 10 | Help and Documentation | 3 | Real market guide exists but is folded away; Modelo vs Provedor is never explained where it appears. |
| **Total** | | **24/40** | **Acceptable** — strong details, unresolved system-level debts. |

## Design Specificity Verdict

**7/10 — authored at the detail level, split at the system level.**

This is not a category-interchangeable skin. Per-row provenance (`Casa · Empate · Fora · Modelo`), the match page's source/update strip, the pre-submit re-quote with old→new prices, the market guide written in the product's own voice, and Portuguese copy that reads as product language all belong to this product. Geist Mono on every price, time and balance, hairline dividers and lime-as-data are a coherent voice.

What holds it back: a soft neon layer (20px radii, glow, gold, promo-card padding) sits on the Precision Noir layer (8px radii, condensed uppercase, mono numerals). The board obeys the second; featured cards, the guest card and the cashier obey the first. The page skeleton is also the standard hero-trio + rail + filter band + card grid, so authorship lives one level down rather than in the composition.

**Deterministic scan.** `impeccable detect --json web/app/page.jsx web/app/layout.jsx web/app/error.jsx web/app/components` returned `[]`, exit 0 — but JSX is regex-matched only. The text mode prints the caveat: element rules (tiny-text, low-contrast) did not run; the result is a coverage gap, not a clean bill. A probe with real HTML fired `low-contrast`, `tiny-text` and `overused-font`, confirming the engine works.

Browser evidence fills the gap: **470 text nodes at 10–10.5px** (462 are the `1/X/2` ticks; 7 live-league markers; one live badge), **0 text-contrast failures** (minimum 6.54:1 dark, 5.09:1 light), **0 page-level horizontal overflow** at 1440/768/390/320, **79 touch controls below 44px at 390px** (78 at 320), and **0 unlabeled interactive controls** (all 156 icon-only controls carry `aria-label`/`title`).

The detector and the design review disagree on the light-theme odds. Measured directly: in light, `.sx-row` and `.sx-odd` are both `rgb(245,245,244)` and the border is `rgba(255,255,255,.05)`. Text stays legible (B is right about contrast), but the button surface disappears (A is right about affordance). This is an affordance defect, not a contrast failure.

**Visual overlays.** None. `impeccable live-server` is absent from CLI v4.7.0, so no user-visible overlay was possible; browser measurements and screenshots are the substitute.

## Overall Impression

The product's detail craft is unusually high: it volunteers where its numbers come from and refuses to silently re-price a bet. The biggest opportunity is not more polish — it is composing the board as a comparison instrument instead of a 27,448px card wall, and finishing the high-stakes moments (betslip, withdrawal, self-exclusion) with the same care as the re-quote.

## What's Working

1. **The price declares its origin.** Each `.sx-odd` is 114×51 desktop / 107×46 phone, with a 10–11px tick, a 15–17px mono price, and an 11px market line that changes to gold when a provider published the number. The hardest promise — this number is ours, that one is somebody else's — is legible in a 60px object.
2. **The re-quote contract.** `placeBet()` fingerprints legs + stake, re-quotes, compares each price, and on a move renders `1.34 → 1.36` with an explicit "Aceitar novas cotações". The idempotent `bet_id` makes a retry safe. It is a design decision expressed as code.
3. **A teaching tone that never sells.** The market guide states that model prices are simulated, favorites are scoped to "neste navegador", and the guest invitation promises only what an account does. No fabricated urgency.

## Priority Issues

### [P1] The board is a 27,448px wall with a ~1,100-stop keyboard path
**What.** 154 fixtures render as 388×271 cards in a 3-column grid at 1440; page height 27,448px (1440), 31,930px (768), 49,899px (390), 49,943px (320), across 65 league blocks and 462 odds buttons. Each row contributes 7 tab stops (star, teams, 3 odds, details, extra markets) with no skip link, roving tabindex or pagination.
**Why it matters.** Operate mode is "compare fixtures and odds". A bettor cannot scan a league as a column and cannot reach fixture 90 by keyboard.
**Fix.** Add a skip link as the first focusable element; make each row one tab stop with arrow-key movement; page each league to 8–10 rows with "Mostrar mais"; memoise rows so the 15s poll does not re-render all 154.
**Suggested command:** `$impeccable layout` then `$impeccable harden`.

### [P1] The guest invitation is a fixed overlay covering live data
**What.** `.guest-login-card` is `position: fixed` at (24,776) 240×100 on desktop and (12,676) on 390, z-index 35, growing to 340px on hover. It covers the first fixture's teams, score or odds at rest; on mobile it adds 98px above the bottom nav.
**Why it matters.** It obscures and intercepts the exact element the page is selling, and expands under the cursor as you approach the board.
**Fix.** Render it inline as a dismissible strip between featured and board (or in the empty right column ≥1281px). Keep the × and `aria-expanded`; drop hover expansion.
**Suggested command:** `$impeccable layout`.

### [P1] The betslip puts the confirm button out of view and cannot be collapsed
**What.** Signed in at 1440×900, the tray is 340×764 at (1080,116); the visible area ends at "Bônus incluído no saldo" and "Confirmar aposta demo" is below the internal scroll. Opening a selection sets `margin-right: 380px`, reflowing the board from 3 to 2 columns and growing the document 27,448 → 32,324px. `betslip-toggle` is hidden ≥1281px, so the only exit is the `×` that deletes all selections.
**Why it matters.** The last 30 centimetres of the task is the least composed part of the flow, and one mis-tap loses the slip.
**Fix.** Pin the submit as a sticky footer; keep total/return visible above it; allow collapse at every width with selections intact; reserve the tray column so adding a bet does not re-lay-out the board; put "limpar" behind an undo toast.
**Suggested command:** `$impeccable layout` then `$impeccable polish`.

### [P1] Withdrawal and self-exclusion execute on one click
**What.** `Sacar agora via Pix` submits immediately; destination is a 12px hint, with no balance, fee, ETA, minimum or post-withdrawal balance. `Autoexcluir-me` runs with a hard-coded `until: "2027-01-01"`, sits 8px from `Sair da conta`, and reports through `window.alert`; bonus claiming uses `window.alert` too.
**Why it matters.** These are the two moments where a user can lose money or access by mis-tap, in a product whose promise is a high-fidelity simulation.
**Fix.** Add a review state (balance, destination with "Trocar", amount, fee, ETA, balance after) and a duration choice for self-exclusion (24h/7d/30d/permanent) with consequences and explicit confirm. Replace every `window.alert` with the in-page notice pattern.
**Suggested command:** `$impeccable harden` then `$impeccable clarify`.

### [P2] Light theme erases the odds affordance and state semantics drift
**What.** In light, `.sx-odd` and `.sx-row` are both `rgb(245,245,244)` with `rgba(255,255,255,.05)` borders, so the three odds read as bare numbers. The active Favoritos chip uses `--bad` (error red). The same price is lime on featured cards and ink in rows.
**Why it matters.** Light theme is a supported surface; its primary interactive object loses its button affordance, and a filter reads as an error.
**Fix.** Add theme tokens `--odd-bg`, `--odd-border`, `--odd-hover` (light: white tile on `#f5f5f4` with `#dfe3e8` border) and a non-error active style for filters. Unify the price colour across featured and rows.
**Suggested command:** `$impeccable colorize` then `$impeccable polish`.

### Also worth fixing
- **P2 "Em alta" fabricates popularity.** `featured` is the first three non-final priced fixtures (`SportsHome.jsx:477`). Rename to "Próximos jogos" or "Em campo hoje". (`$impeccable clarify`)
- **P2 No responsible-gambling line for guests.** `Header.jsx:8` prints `18+` only for signed-in players, and the footer has none; it is hidden below 420px. (`$impeccable clarify`)
- **P2 Zero-result search dead-ends.** Sub-copy stays generic, the query is not echoed, and `Limpar filtros` does not clear the query; the only exit is the 28×36 clear button. Focus is lost after clearing. (`$impeccable clarify`)
- **P2 Tablet touch targets.** At 768, `+9 mercados` is 93×18 and `Ver detalhes` 95×36; 79 controls are under 44px at 390. (`$impeccable adapt`)
- **P3 Password placeholder reads as filled.** `••••••` in an empty field. (`$impeccable clarify`)
- **P3 Cashier corners disagree.** `border-radius: 8px 22px 0 0` on `.sheet`. (`$impeccable polish`)

## Persona Red Flags

**Alex (power user).** Cannot share or bookmark a fixture: detail is state-only, no `pushState`, title never changes; a reload drops the board. Cannot scan a league as a column because prices sit inside 3-up cards. No `/` search shortcut, sort, league jump or page size. The `Mercado` selector silently rewrites every row.

**Sam (keyboard / screen reader).** No skip link; reaching fixture 90 is not viable at ~1,100 row stops. Heading order starts at H2 "Em alta" before the only H1, and the featured section is outside `<main>`. `.sx-odds` groups have no accessible name; live score/minute are unlabeled spans. Search filtering announces nothing (`aria-live` count 0). The mobile betslip is a `section`, not a dialog: no focus trap, no `aria-modal`, no scroll lock. After a failed login, focus stays on submit.

**Casey (390 phone).** 304px of an 844px viewport is consumed before the first fixture (topbar + 119px header + 63px nav + 98px guest card). Three horizontal scrollers show no affordance; the third featured card is a 46px sliver at 390 and 20px at 320. `Filtros` hides four controls behind a 79px card. The bottom nav's third item "Dados" opens a password-gated operator form, which reads as a bug to a normal bettor.

## Minor Observations
1. `CANDIBET.` footer mark plus four links — no age gate, licence, contact, responsible-gambling link or deposit-limit entry.
2. `#search` sits inside a `<label>` that also contains the clear `<button>` — invalid labelable nesting.
3. Two favorites stores (`candi-sport-favorites`, `casa-favs`); the rail count reads only the first.
4. `--gold` equals `--acc` in dark but is amber in light, so the favorite star changes semantic colour between themes.
5. `.sx-sports` is a `<div aria-label>` with no role.
6. "mostrar só ao vivo" both changes its text and sets `aria-pressed`.
7. The account panel exposes the raw `player_id` and prints `Status do sistema: ok` in customer chrome.
8. Cashier offers four rails but only the button label reveals they are demo credits.
9. Help chat has no launcher when closed, and Escape does not close it.
10. Fine detail done right: tabular numerals + mono prices, `scroll-padding-top: 120px`, global reduced-motion.

## Questions to Consider
1. If the fixture card is the atom, does "the same page, taller" survive a Sunday with 900 fixtures — especially on a phone?
2. Would "Em alta" survive a rule that every claim must be computable from the feed? If not, what replaces the strongest visual block on the homepage?
3. Why can a bettor not send a match to a friend, or reopen the one they researched at lunch — and how much of the "research a match" promise is lost to the missing URL?
