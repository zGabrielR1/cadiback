# 0074 — Sportsbook visual identity

The owner liked the previous polish but found its serif typography, spacious
introductory sections and product-like game cards inappropriate for a betting
platform. Replace the editorial opening with a compact functional match
highlight and bring the sports board forward.

Self-host Barlow Regular/Semibold and Barlow Semi Condensed Bold under
`web/public/fonts`, with their OFL licenses. Use condensed uppercase headings,
compact navigation, slate surfaces and lime selection/price accents. Keep
light mode, reduced motion, existing sports pricing attribution and the
guest/login boundaries.

Casino covers are keyboard-accessible direct play buttons. Separate details
buttons retain access to information and favorites. Remove repeated play
buttons beneath every cover. Smaller banners, denser game rows, horizontally
scrolling mobile filters and removal of the duplicate mobile category sidebar
put playable content earlier on screen.

This is a frontend release to the existing linked Vercel project. The backend,
accounts, provider settings and payment/session contracts are unchanged.

Released to https://cadiback-web.vercel.app, deployment
dpl_28bonF8FbAf5U6APohrjvwNhhNmp (READY). Production HTTP/API/font checks
and a live desktop/mobile browser pass succeeded, including odds-to-betslip.
