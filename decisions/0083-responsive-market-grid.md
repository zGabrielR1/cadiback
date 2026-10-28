# 0083: Responsive market grid

Replace the stretched match table rows with responsive cards inside each competition. A card groups state, favorite, teams/scores and full-width decimal odds. Desktop fits multiple cards across; tablet uses two columns when space permits; phones use one. Existing handlers, source labels, filters, league disclosure and authenticated research remain unchanged.

Narrower desktop navigation returns more width to markets. Em alta becomes a horizontally scrollable, snap-aligned strip on phones/tablets instead of three stacked features. The market heading remains visible on mobile. Existing APEX direction and both theme palettes are retained; no new assets, dependencies or invented data.

Validation: production build, structure verifier, core and demo suites, frontend tests, 28 responsive browser assertions. Reviewed all six light/dark screenshots at 1440/768/390. Existing skill inspector CDP failure persists; custom Playwright used. Visual review: composition 8, type 8, colour 8, interaction 8. Main tradeoff: cards use more vertical space per match on phones, but featured markets no longer consume three stacked screens.

Production deployment: dpl_DfvpJ1TQQ4bzxemr5Ag7rLDU9UHJ READY on cadiback-web.vercel.app. Desktop production checks pass; tablet production check timed out waiting for sports feed. Local responsive checks cover all three widths.
