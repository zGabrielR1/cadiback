# 0076 — APEX adapted to Candibet

The owner requested a more prominent bottom-corner login invitation and a
meaningful application of the supplied APEX / Precision Noir direction while
preserving the approved platform identity and spacious authentication design.

## Design decisions

- Keep Candibet's name, Barlow wordmark/display headings and compact sports-first
  hierarchy. APEX is an internal design direction, not a replacement brand.
- Introduce self-hosted variable Geist for interface text and Geist Mono for
  prices, scores, balances and stake/return values. Include their OFL licenses.
- Use layered graphite surfaces, Electric Chartreuse selections/actions, cyan
  informational accents, precise borders and a small family of control/panel
  radii. Preserve a readable light theme.
- Add a restrained vector field behind the existing featured match. Its
  information remains real feed data; no promotional event, sponsor, player
  photograph or unsupported statistic is invented.
- Add a collapsible desktop sports rail for live/favorite filters, actual sports,
  competitions and country/league hierarchy. Tablet and phone retain their
  horizontal filters rather than squeezing the rail into the viewport.
- Give desktop selections a reserved right-side betslip. Tablet/phone use a
  compact summary that expands on request. Escape collapses it and returns
  focus. Invalid stakes and insufficient balance are explained inline. Server
  confirmation remains authoritative; displayed return is explicitly estimated.
- Introduce a shared OddsButton whose temporary arrow is triggered only by an
  actual price change for the same selection. Direction is shown with an arrow,
  not inferred profit/loss, and expires after 1.8 seconds. Reduced motion applies.
- Increase the corner invitation to a clear heading, stronger border and two
  actions. It remains visible while scrolling and is enabled on small screens.
  Dismissal is respected. Login/cashier/chat, builder and selected bets take
  precedence so it does not compete with the active transaction flow.

The supplied prompt supersedes conflicting taste-skill preferences: restrained
ambient treatment in the featured match, layered graphite, numerical mono,
chartreuse selections and softer overlay radii are deliberate. Its call for
large editorial sections is adapted to the user's earlier rejection of a
storefront-like landing page. Dense markets remain structured rows.

## Behavior preserved

Search, sports/date/league filters, favorite fixtures, market expansion, builder
data boundaries, account/signup/social/Turnstile contracts, game launch and
payment APIs retain their existing behavior. The guest confirm action now
explicitly opens login even if signup was the last account mode viewed.

The betslip UI does not create new pricing, settlement or financial state
machines. Backend acceptance/rejection remains in the existing page handlers.
No notifications, historical charts or movement series are fabricated to fill
the design brief.

## Verification

Production build and Node 13/13, core 50/50 and demo 426/426 checks pass. The first
browser pass completed 90 checks without page errors at 1440, 1100, 768, 390 and
320px, covering invitation persistence/dismissal/signup, rail filtering and
collapse, actual font application, slip placement/expansion/validation/return,
keyboard focus and genuine quote-change feedback. Final screenshot review,
compatibility checks and deployment receipt follow after completion.

Visual review: the first pass kept the approved compact hierarchy and gave the
selected prices a clear focal point. It exposed a wrapped tablet login action;
secondary header controls were reduced at that breakpoint. The 57-check
builder/authentication compatibility pass also passed without page errors.

Final verification: the refined 90-check pass, builder/auth 57-check pass and
casino compatibility passed with no page errors or horizontal overflow. Final
phone/tablet/desktop, light and casino screenshots were visually reviewed.

Released to https://cadiback-web.vercel.app on Vercel deployment
dpl_HmwLntZfmXrJLcadUkJonBPzrvCB (READY). Public HTTP/font/health/sports
checks pass (320 fixtures); player access remains protected. Live Chrome checks
confirm both fonts actually loaded, stronger invitation persistence/dismissal,
rail collapse, reserved desktop slip space, tablet summary/expand/Escape focus,
phone invitation and login, with no page errors or horizontal overflow.
