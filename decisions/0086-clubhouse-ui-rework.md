# 0086 — Clubhouse storefront rework

Date: 2026-10-24

## Decision

The owner requested a complete UI rework with Impeccable, confirmed that existing workflows must survive, opened the visual identity, and selected the warm-consumer / Clubhouse direction in the local decision preview. Implementation is code-led.

Replace the green condensed sportsbook presentation with warm stone surfaces, rounded fixture cards, humanist Nunito Sans, and a restrained orange action color. Light is the initial theme for new visitors; existing saved light/dark choices remain. Dark mode uses warm charcoal surfaces and a lighter action color.

The shell now separates navigation from a broad contextual search row. The sports page presents sport filters, two complete featured fixtures and the existing competition-grouped board, with upcoming fixtures, account invitation and competition links in a secondary rail. Mobile retains bottom navigation, horizontally scrollable sport/featured collections and disclosure-based filters. The guest invitation is inline rather than covering markets.

Shared styling extends to match research, advanced research, authentication, profile/session/history, cashier, betslip, data portal, casino and error recovery. The game cover assets, server routes, quote validation, wallet rules, authentication and provider boundaries stay intact. Favorites retain their existing browser storage. New UI icons are small authored SVGs; Nunito Sans is self-hosted with its OFL license.

## Implementation boundary

The new visual system lives in `web/app/clubhouse.css`, loaded after existing integration layouts. Earlier uncommitted work in the repository was retained. PRODUCT.md records the confirmed product scope; the development-only direction contract and review evidence live under `.impeccable/`. No fabricated fixtures, odds or account data were added to the shipped app: screenshot and interaction data comes from local browser interception only.

## Validation

Production static export builds. Structure verification is clean. Core: 50 tests; backend demo: 426 tests; frontend Node test suites pass. Final responsive interaction pass: 117/117 at 1440/768/390/320, no page errors or page overflow, across light/dark discovery plus guest research/auth, favorites/search, account, wallet, slip and gated casino. Design inspector: 0 FAIL / 0 WARN at 1440/768/390. Its warm-palette checks are explicitly allowed because this is the owner's selected direction. Mechanical Impeccable detector returned an empty finding list on the scanned changed UI files.

Independent finish review identified six material fixes: truthful casino prices/banner, readable cover fallback, consistent icons and slip styling, casino content hierarchy, and compact tablet invitation. All were resolved. A resulting mobile fixture-name overlap was resolved in one further scoped correction; its desktop/phone checks pass 8/8. The final reviewer disposition is ship for the scored fixes. DESIGN.md and .impeccable/design.json document the built system.

No new shipping raster was produced or replaced. A read-only provenance scan identified 21 preexisting game-cover files without embedded metadata; this inherited drift was recorded without modifying the assets. No deployment has been performed for this redesign.
