# 0081 — Compact expanding guest invitation

The lower-left login invitation is now small at rest: 240px wide, showing the
account line, a chevron and the two actions. The headline and supporting copy
live in a collapsed body. Hovering the card on a device with a real pointer
grows it to 340px and reveals that body; moving away returns it to the compact
size. Width, padding, body height, opacity and the chevron rotate over 300ms
with one shared easing curve.

Hover is deliberately gated on `(hover: hover) and (pointer: fine)` so a touch
screen never inherits a sticky hover state. Touch and keyboard use the new
toggle button: it carries `aria-expanded`/`aria-controls`, pins the card open on
tap or Enter/Space, and pins it closed on the next activation. The old
scroll-based `is-compact` state is removed — the resting state is now compact
everywhere — along with its scroll listener and selection/exploration calls.

Reliability details: the open card is clamped with
`width: min(340px, calc(100vw - 24px))` on phones, the card never exceeds the
viewport (`max-height` plus the bottom-nav/safe-area offset), the collapsed body
is `visibility: hidden` for assistive technology, and the global
`prefers-reduced-motion` rule removes the transitions while keeping every state
reachable.

Validation: production export build; frontend Node 19/19; `verify.py` 0;
`frame` 50/50; `demo` 426/426. A Playwright pass ran 18 checks locally:
desktop starts at 240px, hover grows past 320px and reveals the body, leaving
collapses it; keyboard Enter expands/collapses with `aria-expanded`; a touch
context taps open to a card that fits the 390px viewport and taps closed again,
with no page errors.

Published to Vercel production: deployment
`https://cadiback-gwx84mb1w-memy2.vercel.app`, aliased to
`https://cadiback-web.vercel.app`. Eleven live checks against the production
host repeated the hover, collapse, touch-open and viewport-fit assertions with
no page errors. The backend was not redeployed (frontend-only change).
