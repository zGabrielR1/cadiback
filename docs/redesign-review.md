# Candibet redesign review

Review date: 2026-10-23. Direction retained: Candibet / APEX Precision Noir.

## Method and scope

Ran the requested `npx skills add Leonxlnx/taste-skill` command for the project,
with non-interactive Codex installation. This time installation succeeded.
The canonical skill is now `.agents/skills/design-taste-frontend`; the package's
`redesign-existing-projects` workflow is integrated into that skill rather than
installed separately. The new instructions match the previously downloaded
copy after normalizing line endings.

Used its existing-app review workflow, app-screen rules and screenshot critique.
Captured the live sports home, scrolled markets, selected betslip, builder,
statistics and login at desktop/tablet widths. A phone visit did not load event
rows within 60 seconds. Repeated the full layout audit at all three widths
using a recorded response from the live sports endpoint, without changing the
deployed page. These repeated measurements isolate layout from feed delays;
they are not availability measurements. No bet, payment or
production login was submitted. Signed-in wallet/casino flows were not audited
in this pass. Source review supplements the public browser observations.

The packaged inspector again timed out at CDP `Page.enable`. Fresh screenshots
and layout measurements use the working Playwright/Chrome path instead. This
is not a claim that the stock inspector passed. Source lint reports five FAIL
occurrences and nine WARN occurrences on the selected files. These include
functional star glyphs and APEX's explicitly requested ambient gradients, plus
numerical mono and real overlay shadows. Retaining the approved brand takes
precedence over mechanically removing those devices. A consistent SVG icon
system is nevertheless a worthwhile refinement.

## Keep these foundations

The graphite/chartreuse hierarchy, recognizable Barlow wordmark/display voice,
Geist interface and numerical text, restrained motion, spacious login, explicit
missing-data states and reserved desktop betslip space are useful foundations.
The next work should concentrate on discovery, reading and transaction feedback.

## Measured baseline

The repeatable pass used one recorded live response and a 900px viewport height.
Positions are page coordinates, not the amount visible after scrolling.

| Viewport width | First ordinary event begins | Featured area height | Team text | Invitation share of viewport |
| --- | ---: | ---: | ---: | ---: |
| 1440px | 801px | 275px | 12px | 8.3% |
| 768px | 923px | 285px | 12px | 15.6% |
| 390px | 1005px | 335px | 11px | 21.9% |

The featured match has usable odds above the ordinary list. The problem is
browsing depth, not a total absence of first-screen betting controls. No
horizontal overflow or browser page exceptions were observed in this repeated
pass. The collapsed phone slip exposes the count and an Open action, but not a
selection or stake summary. Artifacts: `.taste-skill/redesign-review/`.

## Priority 1: Bring the useful markets forward

The home screen spends substantial height on the header, workspace navigation,
featured match, title, sport/date/competition controls and another live filter
before the ordinary event list. Scrolled market screenshots show that the
interface becomes useful once those introductory layers leave the viewport.

Recommended changes:

- On phones, reduce the featured match to a compact live-event strip. Keep the
  full expressive composition on larger screens only when it earns its space.
- Put the live/upcoming choice next to the sport control and move secondary
  filters into a clearly labeled filter sheet with a selection count.
- Display one primary market per event by default. The current result and total
  markets stack vertically, with two further actions beneath them. This makes
  rows tall and leaves large horizontal voids between teams and prices.
- Let a market selector switch the board between result, totals and other
  supported groups. Extra markets remain expandable.

Acceptance target: at 390×844, after dismissal of the invitation, an ordinary
match and its primary odds should be usable without an initial page scroll.
At desktop width several meaningful event rows should fit in the first screen.
Preserve competition grouping and readable team names rather than shrinking text.

## Priority 2: Make the opened match a coherent workspace

The builder currently changes the page while retaining a separate dropdown,
match summary, market tabs, statistics and draft. A user can access these pieces,
but the transition could establish stronger context.

Recommended changes:

- Make the team/event identity an obvious entry into match detail, alongside
  the existing “Criar Aposta” action.
- Use a compact persistent match header with competition, score/state and a
  clear return to the previous list position.
- Give Markets, Statistics and Draft the same navigation model across widths.
  The phone panes already provide a useful foundation.
- State data coverage alongside the match: current counts, player markets,
  unavailable historical data and last successful refresh.
- Rework narrow quote buttons so long team/player labels cannot compete with
  the number. The 390px builder screenshot shows the last result selection
  crowding its price at the panel's right edge. A label-above-price layout or
  an adaptive column count is safer than assuming three wide labels will fit.
- Prefer a featured match with useful available information and active markets;
  the current first-live-fixture choice can emphasize an old match near its
  time cap while a better-covered match sits farther down the list.

Acceptance target: users can open a match, inspect its evidence, select a market
and return to their previous discovery context without losing orientation.
Unavailable historical/player statistics remain explicitly unavailable.

## Priority 3: Complete the transaction experience

The visual betslip is ahead of its transaction feedback. Source review confirms
that `placeBet` still uses browser alerts for acceptance and rejection. The
collapsed phone slip shows a count and “Abrir”, without event/selection or stake
context.

Recommended changes:

- Keep validation, rejection and retry feedback in the betslip itself.
- Show a server-confirmed receipt with reference, accepted stake/odds and a
  history action. Clear selections only after confirmed acceptance.
- Add a short selection/stake summary to the collapsed phone bar so its state
  remains understandable without opening it.
- Introduce explicit changed-quote and suspended-market review states backed
  by current server quotes, not just a changed-color button.

There is also a concrete consistency issue to resolve before presenting this
as a completed betting workflow. The builder correctly refuses to invent a
same-match combined price. The ordinary board's `selectBet` can nevertheless
append several picks from the same fixture; its betslip multiplies all prices.
`demo/server.py::bet` likewise multiplies submitted leg prices after range
validation, without enforcing a same-match correlation policy or obtaining a
fresh quote in that path. This is a source finding, not a production-bet test.

Use one policy across all entry points: reject unsupported same-match
combinations, distinguish mutually exclusive selections, and obtain a valid
server quote before presenting an accepted price. This needs backend work as
well as UI work. It cannot be solved honestly with styling alone.

## Supporting refinements

### Preserve the assertive invitation while protecting active reading

The stronger corner invitation is an explicit owner preference and should stay.
Its first appearance is effective, but the screenshots show it covering parts
of the sports rail and match list. Keep that entrance, then consider a compact
corner state after a user starts filtering or comparing. Keep dismissal and
the existing precedence for login/betslip/builder work. Do not auto-open a modal
or repeatedly restore a dismissed invitation.

### Improve density through structure, not smaller text

Phone CSS currently sets team names to 11px and some market metadata to 9px.
Reclaim height from repeated controls and secondary markets, then use a more
comfortable reading size for teams and market names. Keep numerical columns
aligned. Replace mixed star/emoji-like controls with one restrained SVG set.

### Edit the product copy and consolidate the component language

The source still contains casino banners describing “100% fidelity”, “replica”
and implementation-oriented payment simulations. Rewrite these around actual
player tasks and accurate states. In particular, payment speed must not be
promised where provider confirmation is still pending.

After the flow improvements, consolidate the accumulated global/workspace/APEX
overrides into reusable tokens and components. The goal is consistent states
and spacing for the next feature, not a fresh palette or another typeface.

## App-screen critique

1. **Dominant answer:** the first screen communicates sports and a featured
   quote, but its largest mass still answers the introductory question more
   strongly than the discovery question.
2. **Grid and edges:** the major frame is coherent. Event rows have avoidable
   vertical expansion and horizontal voids; narrow builder quotes need a safer
   relationship between the identity label and its numerical value.
3. **Color:** the approved palette is recognizable. Accent should continue to
   distinguish selected prices and the current action, rather than expanding
   into more decorative navigation or badges.
4. **Figures:** prices align and use loaded numerical type. Individual stake
   arithmetic is understandable; unsupported correlated-leg multiplication is
   a separate policy problem documented above.
5. **Zero and missing:** the statistics table correctly differentiates zero
   from a dash. Keep this behavior and make coverage easier to understand.
6. **Charts and legends:** no unsupported historical chart is drawn. Add a
   visualization only when it answers a real question from supplied data.
7. **Phone:** navigation folds and the slip has a usable expanded state. The
   ordinary event list arrives too late, and the collapsed slip lacks context.

No redesign score is invented from the failed stock inspector. The concrete
measurements, screenshots and source findings above are the review evidence.

## Proposed order

1. Shared selection/quote policy and inline betslip state model.
2. Mobile first-screen compression and denser event/market structure.
3. Coherent match detail and data-coverage navigation.
4. Invitation engagement state, icon/readability cleanup and product copy.

This review installs the skill and records recommendations. It does not change
the application or replace the currently approved production deployment.
