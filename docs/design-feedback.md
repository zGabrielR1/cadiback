# Owner feedback — 2026-10-23

Recorded before renewing GitHub authentication for publication. Implemented in release 0078: sport-first discovery, selected-event detail context, sport-specific research, darker low-contrast surfaces and reduced radii. See decision 0078 and CURRENTTASK for validation and deployment.

- **Rounding:** the interface is somewhat too rounded. Reduce radii on structural containers and controls while preserving the current Candibet identity.
- **Dark mode:** the lighter revision went too far. Return to darker surfaces and reduce harsh contrast between adjacent backgrounds, borders, text and accents. The desired change is softer contrast, not a lighter overall theme. Preserve readable text and clear selected states.
- **Criar Aposta discovery:** begin with all sports, rather than a soccer-only flow or an unexpected full match list after selecting a match. Use a sport → relevant events → selected event detail flow. A selected match should keep the user in that match's context.
- **Sport-specific research:** adapt statistics, market groups and terminology to each sport. Do not display soccer concepts such as red/yellow cards on sports where they do not apply. Render only supported data and actual available markets; describe missing coverage without inventing numbers or prices.
- **Preserve what works:** retain the useful match research, explicit same-match combination limitation, quote review and confirmed transaction behavior.

Implementation acceptance: every available sport is discoverable; event selection opens only that event's relevant research; back navigation preserves sport/filter context; incompatible statistics are absent; absent data has an honest empty state; the visual revision is darker but less stark, with less rounding.
