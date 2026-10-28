# Product

<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
Portuguese-speaking sports followers exploring current fixtures, comparing odds, and researching matches. Signed-in players also manage selections, account, wallet and gated game experiences.

## Product Purpose
A personal high-fidelity betting platform simulation. Public discovery leads from sport and competition to fixture detail and supplied markets; authenticated workflows retain their existing transaction behavior.

## Operating Context
Next.js 16 / React 19 static-export storefront backed by the Python API. Both dark and light themes and responsive desktop, tablet and phone use are supported.

## Capabilities and Constraints
Preserve public sports-first discovery, search, filters, live fixtures, favorites, match detail, source/model distinctions, refresh/retry states, authentication, account, wallet, betslip and gated casino/data portal workflows. Preserve server validation and all existing integration contracts. Do not fabricate stats, market popularity, volume or promotional claims. The user confirmed that the entire UI may be redesigned with a new visual identity.

## Brand Commitments
Keep the Candibet name and Portuguese interface. The user authorized the improved original green/near-black interface for production and a separate local Tournament Blue build matching the pinned decision sketch. Normal builds must remain Original, without an appearance selector or query/storage activation. Blue is compiled only with NEXT_PUBLIC_LOCAL_BLUE=1, built and served through scripts/local_blue.py with an isolated temporary export and local account data; it is not deployed. Both support light/dark themes. Clubhouse and the earlier shared-app appearance selector are superseded development history.

## Evidence on Hand
Existing components under web/app/components; local fonts and assets in web/public; architecture, progress and decision records; sports feed and provider catalog fixtures under probes. AGENTS.md describes a personal hobby simulation; real provider integrations exist and their semantics must remain intact.

## Product Principles
- Make fixtures, markets and their provenance easy to compare.
- Keep public research accessible before account entry.
- Preserve working behaviors and transaction rules during visual changes.
- Represent missing, stale, loading and failed data honestly.
