# 0075 — Match research, selection drafts and spacious authentication

The owner requested a “Criar Aposta” menu with deeper match/team/player
information, a more spacious login, application of Leonxlnx/taste-skill,
design-learning documentation and deployment.

## Product behavior

SportsHome has a persistent “Criar Aposta” menu and a direct entry on each
football fixture. The workspace provides match selection, per-team current
fouls/cards/corners/shots/possession, grouped markets, scorer selections when
supplied, and a selection draft. On phones, Markets, Statistics and Draft are
separate panes rather than a long stack of panels.

Missing data stays missing; confirmed zeros remain zero. Team historical
averages and player-level fouls/cards/shots are explicitly unavailable. Team
counts are never confused with the market's match-wide totals. Quotes retain
their provider/model label. A draft is reconciled against the current fixture
on refresh, dropping unavailable selections and using current prices.

No same-match combined quote is invented. The combination action is disabled
with an explanation. A supplied selection can replace the existing betslip as
one single bet, without multiplying correlated selections. Ended matches,
refreshes and failed feeds cannot dispatch new builder selections.

Authentication keeps the existing PF/PJ, social login, password recovery,
Turnstile and remember-device contracts. It adds a semantic form, Enter
submission, password visibility, a larger desktop dialog and more generous
field/group spacing. Tablet and phone use one form column. Existing dialog
focus containment, Escape, restore-focus and background-scroll behavior remain.

Help is available in the top bar and footer; its closed floating launcher no
longer covers odds. Sports and casino banner surfaces are flat. The approved
Barlow/slate/lime identity is retained.

## Skill and rationale

The requested `npx skills add Leonxlnx/taste-skill` flow was attempted
non-interactively for Codex. Git's schannel credentials failed. The skill
installer's public-repository direct-download fallback succeeded into
`.agents/skills/taste-skill`; its SKILL.md and complete app-screen reference
were read and applied during this turn.

App style: Data terminal, seed 501942732, palette/type kept. The existing
navigation and brand take precedence over replacing the shell with an icon
rail. See [UI agent learning](../docs/uiagentlearning.md) for the actual process,
data boundaries, adopted principles and deliberate exceptions.

The stock inspector failed twice at CDP `Page.enable`; no clean stock-inspector
result is claimed. Source lint and the working Playwright/Chrome path provide
the measured and visual checks. The lint warnings for an actual floating
dialog shadow and missing-value dashes are appropriate for their semantics.

## Visual critique

Round 1: The main question is clear: compare this match and prepare selections.
The three desktop panels share one grid, figures align, and missing values
remain distinct from zero. The strongest remaining problems were tablet form
compression, mobile statistics buried after the draft, and redundant close
controls in authentication. Fixes: single-column tablet dialog, explicit phone
pane navigation, and one close affordance at the top of authentication.

The market workspace deliberately favors evidence and legible controls over
imagery or decorative motion. No generated page-style creativity score is
claimed for a betting tool.

## Verification

Production build, 13 Node tests, 50 core tests and 426 demo regressions pass.
The initial browser pass completed 57 checks without page errors. Final
viewport review completed another 57 checks without page errors at 1440, 768,
390 and 320px, including mobile pane switching, supplied/missing players,
draft clearing on match change, single-bet transfer, password visibility,
one Enter submission with inline API failure, PJ signup and Escape.
Light mode also fits the viewport. Desktop/tablet/phone and empty/signup
screenshots were visually reviewed. Structure and deployment preflight pass.

Round 2: The tablet form now has the same comfortable text measure as desktop.
On phones statistics are one click away and each pane has the full content
width. The layout has no horizontal page overflow. Price and player data stay
scoped to the selected match; confirmed zero and missing values remain distinct.
The remaining product limit is data coverage and same-match joint pricing,
shown explicitly instead of obscured by decorative content.

Released to https://cadiback-web.vercel.app on Vercel deployment
dpl_E3Nt2zBhdtb4aHCfNAWhHhrEJy4v (READY). Production HTTP checks passed
for the menu, healthy API proxy, 320 fixtures, Google/Facebook providers and
protected player 401. A live Chrome pass found 167 football options and eight
scorer selections on the inspected match. Single-bet transfer, country search,
phone statistics, login focus/form/provider rendering and Escape passed with
zero page errors and no horizontal overflow. Production screenshots reviewed.
