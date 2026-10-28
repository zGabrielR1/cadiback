# 0078 — Sport-first research and quieter dark mode

The owner clarified that dark mode should remain dark while reducing harsh contrast; the preceding revision was too light and too rounded. Dark surfaces now use closely spaced charcoal layers, softened foreground/accent colors and restrained radii (up to 8px in the APEX components).

Criar Aposta no longer defaults to soccer or silently picks a match. Its entry point lists all sports present in the feed. Choosing a sport reveals only its events; choosing an event replaces discovery with that event's research. Breadcrumbs return to sports or the selected sport's event list. Direct event links from the board work for every sport. Global search filters discovery, while an already selected event retains its context.

`sportProfile` owns research groups, statistic labels and total-market terminology. Basketball uses points/rebounds/fouls; tennis uses aces/games; other known sports have corresponding profiles and feed aliases. Soccer-only mechanics are excluded from incompatible sports. Unknown sports retain supplied result markets and an explicit detailed-statistics empty state. No statistics, prices or combined same-event odds are invented.

Validation: build and structure check; Node 16, core 50, demo 431 tests; 49 browser assertions at 1440/768/390/320, including sports discovery, event context, basketball/tennis semantics, radii and overflow. Transaction regression confirms explicit price acceptance, stable retry identity and mobile receipt. Production publication is recorded in CURRENTTASK.

The server was published from GitHub commit c5aa90e; this frontend-only follow-up is deployed directly from the local Vercel bundle. Render's fallback static frontend consequently remains at the previous revision; the canonical frontend is cadiback-web.vercel.app.
