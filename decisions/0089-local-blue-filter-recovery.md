# 0089 — Make local Blue filter state visible and recoverable

The owner approved a focused local refinement of Tournament Blue, preserving Original as the production default and requiring review before publishing.

Blue hid competition/favorites settings in its closed Filtros disclosure. Its reset action left live-only enabled, so combining live and upcoming filters could leave an empty board after reset. Blue now lists removable active filters beneath the toolbar and provides Limpar tudo. Blue reset actions clear live, date, league, favorites-only and query while retaining sport, market view, saved favorites and bet selections. Original reset behavior is unchanged.

A controlled 110-character unbroken query exposed an empty-state overflow at tablet width. Blue heading and empty-state text now wrap anywhere, as do filter labels; mobile filter buttons have 44px minimum height. Existing typography, palette, layout and build-time isolation remain.

Validation: both builds pass; verify zero problems; core50/backend426 pass; six Node test files pass. Browser72/72 with controlled fixtures across1440/768/390/320, dark/light, covers filters/empty recovery/keyboard/details/expanded markets/guest login/authenticated selection preservation. Original isolation browser check passes with stale appearance preference and query. No real account, bet or payment submitted. Inspector0FAIL/2WARN (inherited micro-label and label density, loading captures only); mechanical detector no findings. Screenshots and assertions are in .impeccable/review/blue-refinement/.

Local review only: http://localhost:8766. No deployment.
