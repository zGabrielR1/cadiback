# 0087 — Original default and Tournament Blue alternate

Date: 2026-10-24

## User decision

After trying Clubhouse, the owner preferred the pre-rework UI and authorized restoring it with targeted improvements, plus building the already-presented blue concept. This supersedes the visual choice in 0086. Preserve the original green/near-black identity as the default; do not treat the blue alternate as another forced replacement.

## Implementation

The shell offers a labeled `Visual` selector with `Original` and `Azul`. Appearance is stored under `casa-design`, separately from the existing `casa-theme` light/dark preference. Direct `?visual=classic` and `?visual=blue` links override a stored appearance; invalid choices fall back to the stored value or Original. Switching is client state only and preserves authentication, filters, favorites, research view, expanded markets, selection and stake state. Blocked browser storage does not prevent switching or direct links.

Original again imports globals/workspace/apex as its base, restores the compact top bar and contextual header search, three highlights, left sport/competition navigation and market-card board. Blue uses scoped tokens and geometry in variants.css: graphite/cool white/ultramarine, a full-height left rail, two paired-team highlights and aligned fixture/price rows; phones reflow to readable cards and sport tabs. Both retain light/dark support and the existing public sports-first/gated access boundary.

Clubhouse CSS is no longer imported. Its source and prior design record were archived locally under `.impeccable/archive/clubhouse-0086.tar.gz`; no git reset or checkout discarded the owner's preexisting work. The reviewed casino price-truth/fallback fixes, account summaries and error recovery remain. No backend or transaction rule changed, and no new shipping raster was produced.

## Validation and release

Production export, structure verification, core 50 tests, demo 426 tests and frontend 19 tests pass. Local browser checks: 127/127 across 1440/768/390/320, both appearances and themes; 48 screenshots. Includes preservation across appearance switching, direct-link/preference precedence, blocked-storage recovery, public research, auth, wallet, slip, casino and feed states. Zero page errors or horizontal page overflow. Controlled data exists only in the browser verification harness.

Independent visual review and final dual-variant design documentation are being completed. No production deployment performed. The local combined application serves the actual feed and current exported UI on port 8765, using a separate temporary data directory for testing.
