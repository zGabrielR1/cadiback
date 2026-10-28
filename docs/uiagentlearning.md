# UI agent learning: designing Candibet

## Start with the job

A sportsbook is used to scan a match, compare evidence, choose a market and
review a bet. Its hierarchy should follow that sequence. The previous serif
headlines and long introduction were polished but delayed the actual job.
The owner preferred the later compact Barlow, slate and lime direction.
That preference is evidence to preserve, not a reason to start over when a
new design skill arrives.

For this release the screen's question is: **What can I learn about this match,
and which supplied selections can I use?** The login's question is simpler:
**How do I get back into my account?** Each gets its own density.

## What the taste skill added

Source: [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill), installed
in `.agents/skills/taste-skill`. Read `SKILL.md` and the full
`references/app-screens.md`. This is an app screen, so its app rules apply;
the marketing-page requirements for photographs and elaborate scroll motion
do not.

The app draw selected **Data terminal**, seed **501942732**, with
`--keep palette,type`. The important move is restrained selection indicators
and aligned figures. The face is the existing Candibet wordmark and Barlow;
the signature element is the paired team-statistics table beside the actual
match markets and draft.

Useful principles applied:

- Put evidence next to the decision. Match statistics and market selections
  share one workspace instead of hiding behind an undifferentiated list.
- Spend accent color sparingly. Builder tabs and selected quotes use a thin
  lime indicator; most figures and controls remain neutral.
- Keep figures tabular and right aligned. A confirmed zero is a real number;
  a missing card count is a dash with an explanation.
- Use flat surfaces. Remove decorative gradients from the sports highlight
  and casino banner, and remove the closed floating help launcher that covered
  betting content. Help remains in the top bar and footer.
- Design each density deliberately. Markets are compact; authentication uses
  larger fields, consistent vertical gaps, a readable text measure and a wider
  desktop dialog. The phone gets one column.
- Treat empty, loading, error, disabled and stale states as part of the design.
  Unavailable information should remain legible and say what is missing.

The skill is a decision aid, not an independent source of product requirements.
Its proposed icon rail and complete dark-palette replacement would conflict
with the owner's approved sportsbook shell. They were not applied. The builder
uses the style within that shell. This is a documented brand constraint,
not an attempt to claim every library preference was followed.

## Content truth is part of visual quality

The live feed snapshot inspected for this release contains fixture identities,
score/time, some per-team match statistics, and priced markets. Some games
have fouls, yellow cards, corners and scorer selections; others have none of
those. The UI reads the supplied data rather than making every match look
equally complete.

| Information | Current treatment |
| --- | --- |
| Team fouls, yellow/red cards, corners, shots, possession | Show supplied current-match counts; missing values remain dashes |
| Player to score | Show actual selections from supplied `scorer-h`/`scorer-a` markets |
| Player fouls, cards, shots | Explicitly unavailable; no fabricated player table |
| Team averages from recent games | Explicitly unavailable; current counts are never presented as averages |
| Individual market quote | Identified as provider or model; can be used as a single bet |
| Same-match combined quote | Unavailable until an actual joint-price service exists |

Multiplying individual prices does not create a valid quote for correlated
selections from the same match. A draft may hold several ideas, but its combined
price remains unavailable. “Usar como aposta simples” replaces the previous
betslip with one selection. Refreshes revalidate the market, player and price;
withdrawn selections cannot be sent to the betslip.

## A repeatable design process

1. Inspect the actual data and existing interactions before drawing screens.
2. State the screen's question and its next action in one sentence.
3. Preserve the parts the user already values: here, typography, palette and
   the familiar sportsbook navigation.
4. Write the content and states before adding visual decoration.
5. Choose a grid that fits the content. The builder uses a comparison column,
   flexible markets and a draft rail; narrower widths collapse the grid.
6. Distinguish deliberate space from leftover space. A login benefits from
   22–28px field/group gaps; a market list rarely benefits from a large banner.
7. Check actual screenshots, not just CSS. Look for covered prices, ragged
   columns, cramped labels, missing values that resemble zero, and hidden actions.
8. Test the interaction implied by each visual state. A selected quote must
   add/remove a selection; a disabled combination must explain why.
9. Recheck the deployed site. Local success alone does not prove the published
   fonts, API proxy or responsive layout work.

## Verification and limits

The skill's stock browser inspector was attempted twice. Its CDP connection
timed out at `Page.enable` in this environment. That is a tooling failure,
not a clean design audit. A working Playwright/Chrome path is used for viewport
screenshots and functional checks instead. The unmodified source linter is
also run. An overlay shadow is appropriate for a floating login dialog;
repeated dashes are legitimate missing-data notation, not prose decoration.

Synthetic fixture/player data belongs only to local browser tests. The
deployed UI uses the real sports endpoint. Browser tests mock authentication
failure and do not sign into or move money on a production account.

Visual critique and final verification results are recorded in decision 0075.

## Applying a new art direction without losing the product

The APEX refinement in decision 0076 tests a second design lesson: a design
brief is a hierarchy of intentions, not a list of effects to apply everywhere.
“Precision Noir” fits Candibet when it improves market scanning, selections and
transaction review. It would contradict the owner's feedback if it restored
the long storefront introduction or replaced the recognizable brand.

The retained anchors are the name, Barlow display voice, compact match-first
layout and spacious authentication. The changed layers are graphite surfaces,
Geist interface text, Geist Mono figures, chartreuse selected states, restrained
cyan information and a context-sensitive betslip. A vector pitch behind the
real match supplies atmosphere without needing a fabricated sports photograph.

The more assertive login invitation remains a corner invitation: larger type,
clearer edge and two actions, with an explicit dismissal. It never opens a
login dialog on its own. Active betting/account work gets priority.

The practical rule is to put visual emphasis on the next decision, not on every
surface. A selected odd can be vivid while the neighboring odds stay neutral.
A genuine quote update earns a brief directional arrow; an unchanged price
earns no animation. An expanded betslip earns the space it needs; a collapsed
phone summary leaves the markets visible.

## Review after the visual identity settles

The [redesign review](redesign-review.md) applies the skill to the current app
without changing its approved identity. Its most useful finding is measurable:
the ordinary match list begins at 1005px on a 390px-wide phone in the recorded
layout pass, even though the featured match is already usable above it.
This shifts the next design task from adding treatments to making browsing
faster. The same review catches crowded long labels and a mismatch between the
builder's combination policy and the ordinary slip. Good visual design must
keep following the interaction and data model after the initial polish lands.
# Follow-up: softer dark mode and transaction clarity (0077)

Owner correction (0078): reducing harsh contrast does not mean raising the entire palette's luminance. Return to dark charcoal, keep adjacent surfaces close in tone, soften white text and lime highlights, and preserve accessibility. Radius is another source of tone: reducing major surfaces to 8px helped the sportsbook feel more precise. Research navigation must reflect the domain: start with sports, then events, then selected-event research; use per-sport statistics rather than recycling soccer labels.

Dark mode does not need near-black surfaces. Raising graphite surface luminance and softening the accent keeps the established identity while making the page less stark. Preserve the difference between canvas, navigation, event rows and selected odds.

Measure access to the first ordinary event, not only the hero. On phones, substitute a compact useful match highlight and disclose secondary filters. Dense markets work best with one comparable market per row; research details can carry the wider coverage.

Design quality includes the data contract. Unsupported same-match combinations must be explicit in every entry point. Changed odds need a review action; a receipt requires server acceptance. A retry must retain its request identity even when the feed changes after the original response is lost.

Keep long player names and the numerical quote in separate layout rows. Compact the corner invitation after engagement so its initial prominence does not permanently obstruct browsing. Test the accepted receipt on mobile: collapsed-slip CSS can accidentally conceal an otherwise complete confirmation.

