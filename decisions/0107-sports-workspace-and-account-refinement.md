# 0107 — Sports workspace and account refinement

Date: 2026-11-06. Status: verified locally; deployment in progress.

## Scope

- Keep Candibet’s red mark, Archivo headings and Source Sans 3 text. Give
  the sports board a white sheet against quiet navigation, align the market,
  date and filter controls, and mark the score card driving the detail pane.
- Keep tablet research below the board at 761–1000px. On phones remove the
  duplicate highlight strip and shorten the heading area so matches appear
  earlier; retain full-width controls and horizontal sport navigation.
- Move social access above manual login/signup. Use full-width, consistently
  aligned provider rows with X, a clear manual-form separator and a quieter
  account-mode underline. Keep the existing validation, reset, Turnstile and
  account/session contracts.
- Add Ctrl/Cmd+K search, guarded while any modal is open. Close extra filters
  on outside pointer input; Escape closes them and restores summary focus.
- Give dark mode neutral surfaces and keep the brand hue for live data and
  primary actions. Replace the logo’s gradient bars with flat CSS geometry.

## Design evidence

Applied design-taste-frontend’s app-screen workflow. Framed sheet, seed
1562621618; existing palette/type retained, no redraw. The main question is
“Which match and market should I inspect?” The signature is the linked live
score strip and match detail pane; the brand supplies the red data accent.
Account access answers “How do I enter my account?” with provider actions
before the manual form. No fabricated figures or new imagery.

Screenshots reviewed at 1440, 768, 390 and 320px, in light and dark themes.
The first pass exposed a tablet grid conflict, which was fixed; phone
highlights were removed after they pushed the first match below the viewport.
Local evidence is in ignored `.taste-skill/`.

## Verification

- Core 50 and backend 427 tests pass. Frontend 58 tests and 73 static component
  renders pass. Structure verifier: zero problems.
- Main production export and an isolated export built from HEAD plus exactly
  these four changed frontend files pass. Unpublished cache/feed changes and
  unrelated tooling deletions are excluded from the release.
- Controlled Playwright checks on the isolated export: 51 pass, no page
  errors or write requests. Covered board/dialog overflow, social visibility
  and order, search shortcut/modal guard, filter open/Escape/outside dismissal,
  selected-score identity and modal close at all four widths.
- Browser fixtures are captured public feed/config. Turnstile is disabled
  only in intercepted test responses; production configuration is untouched.
- Skill lint: zero failures; warnings are existing time formatting, navigation
  group labels, explicit `backdrop-filter:none`, overlay shadows and copy.
- Skill inspector: zero failures at 1440/768/390. Its separate browser has no
  mocked API, so it measures the real empty/error shell and warns about spare
  first-screen space. Populated layouts were inspected through Playwright.

## Deployment

Pending publication and live smoke checks. No schema or backend behavior
change; existing X/Google/Facebook configuration is preserved.
