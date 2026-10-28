# DESIGN — Candibet Sports desk

## Identity
Approved by the owner on2026-10-25. Register: system. Daylight sports desk: compare fixtures and retain context, with no cinematic peak. Signed-out visitors see sports and research; private controls appear only after validated login.

## Tokens
The normative implementation is web/app/auteur.css. Ground oklch(.975 .002 260), card white, ink oklch(.22 .012 260), muted oklch(.47 .015 260), line oklch(.87 .006 260), accent oklch(.54 .20 28), accent-soft oklch(.965 .015 28). Dark ground .19/.009/260, card .235/.009/260, ink .96/.003/260, muted .76/.009/260, line .37/.01/260, accent .76/.14/28 and accent-soft .29/.045/28. Use semantic variables --paper/--card/--ink/--mut/--line/--acc/--acc-soft/--on-acc across every screen.

## Typography
Archivo100–900 for display/match headings; Source Sans3 200–900 for text, labels, forms and tabular numerals. Both self-hosted woff2 with OFL texts. Headings28–40px, contextual teams22–24px, rows15–17px, controls14px, metadata11–13px. No new decorative font.

## Layout
Desktop: sports rail, flexible comparison board,280px context desk. Mobile: horizontal sports tabs, stacked rows and context, fixed bottom navigation. One row per fixture, full provenance and honest missing-data copy. Account uses section navigation and readable balance type; cashier uses the same fields plus an explanatory context column. Dialog forms retain comfortable spacing. Real cover art and existing game canvases remain in the gated terminal.

## Component/state contract
Reuse action/bordered/text/icon/odds/navigation/row/score button roles. Shared input/search/stake and compact/form select recipes. Components inherit active theme variables; new variants require updating this contract first. Current/pressed/disabled/busy/focus state must remain explicit. Every focusable control has2px accent outline with3px offset; search includes its own focus outline. Disabled controls use solid muted text and a dashed boundary, never low-opacity text. Buttons44px on touch; long terms wrap rather than widening the page.

## Guest boundary
No wallet/account/betting menu, balance, betslip or guest betting invitation. Entrar is a neutral sign-in door. Public prices lead to research; selecting/submitting requires existing authenticated flows. No sample fixtures or balances ship. Existing API validation and payment/session rules remain authoritative.

## Motion
Zero scroll families. UI transitions120ms ease-out; modal surfaces retain focus/escape/backdrop behavior. Reduced motion removes displacement. No new shader, autoplay media or sounds.

## Editing protocol
Read this file and the relevant component/state before edits. Keep source/model distinctions and last-successful feed retention. Verify all affected public/member states at1440/768/390/320 with screenshots, build before release, and preserve server transaction semantics. The older Original and local Blue documents are history, not the normal build's current identity.

## 0092 interaction repairs

The owner requested restoration of missing member casino/builder navigation and less verbose account design. Authenticated access is sufficient for casino/catalog; the optional portal code is independent. Header and mobile member navigation expose Criar Aposta. The wordmark is a real root anchor and performs a document reload.

Account uses an identity header and four icon tabs (profile/devices/history/protection), with accessible labels and tooltips. Deposit/withdraw icons select the appropriate cashier tab. Preserve essential financial labels and explicit confirmations. The slip does not cover account/casino; selections remain in application state.

Main sports default to five and fixtures to eight; explicit controls disclose others/more. Explore can collapse, and its sticky list is viewport bounded. Loading skeletons, six-second slow request recovery, failed-request retry and a genuine empty-calendar state replace blank waiting. Retries abort old requests; stale successful feed data remains visible. Catalog failure has its own recovery card.

Pointer/keyboard resize handles persist slip dimensions and desktop search width with viewport clamps. Search expands deliberately; a ResizeObserver keeps floating slip position below the current header. Arrow keys adjust size, Home resets; touch-width search remains full width.
