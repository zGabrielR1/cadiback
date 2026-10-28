---
"name": "Candibet — Original and Tournament Blue"
"description": "Production Original and a separate local Tournament Blue build."
"colors":
  "original-dark-paper": "#0c0c0d"
  "original-dark-night": "#080809"
  "original-dark-card": "#1b1b1d"
  "original-dark-card2": "#141415"
  "original-dark-field": "#101011"
  "original-dark-chip": "#262628"
  "original-dark-ink": "#e7e7e9"
  "original-dark-mut": "#aaaab0"
  "original-dark-line": "#ffffff18"
  "original-dark-acc": "#b9f34b"
  "original-dark-acc-soft": "#25331a"
  "original-dark-on-acc": "#172207"
  "original-dark-data-accent": "#b7c99a"
  "original-dark-bad": "#f195a0"
  "original-dark-bad-soft": "#2a1414"
  "original-dark-gold": "#b9f34b"
  "original-light-paper": "#fafaf9"
  "original-light-night": "#1c1917"
  "original-light-card": "#ffffff"
  "original-light-card2": "#f5f5f4"
  "original-light-field": "#fafaf9"
  "original-light-chip": "#f5f5f4"
  "original-light-ink": "#1c1917"
  "original-light-mut": "#606977"
  "original-light-line": "#dfe3e8"
  "original-light-acc": "#15803d"
  "original-light-acc-soft": "#f0fdf4"
  "original-light-on-acc": "#ffffff"
  "original-light-data-accent": "#17657b"
  "original-light-bad": "#b91c1c"
  "original-light-bad-soft": "#fef2f2"
  "original-light-gold": "#b45309"
  "blue-dark-paper": "#111214"
  "blue-dark-night": "#111214"
  "blue-dark-card": "#1e2023"
  "blue-dark-card2": "#191b1e"
  "blue-dark-field": "#16181b"
  "blue-dark-chip": "#292d35"
  "blue-dark-ink": "#f4f5f7"
  "blue-dark-mut": "#adb2bd"
  "blue-dark-line": "#34383f"
  "blue-dark-acc": "#8198ff"
  "blue-dark-acc-soft": "#29345b"
  "blue-dark-on-acc": "#121b38"
  "blue-dark-data-accent": "#bcc8ff"
  "blue-dark-bad": "#f2a0ae"
  "blue-dark-bad-soft": "#38232b"
  "blue-light-paper": "#f1f3f7"
  "blue-light-night": "#e6eaf2"
  "blue-light-card": "#fff"
  "blue-light-card2": "#f9fafc"
  "blue-light-field": "#f1f3f8"
  "blue-light-chip": "#e5e9f2"
  "blue-light-ink": "#1a2130"
  "blue-light-mut": "#596478"
  "blue-light-line": "#d5dbe6"
  "blue-light-acc": "#3152d1"
  "blue-light-acc-soft": "#e5ebff"
  "blue-light-on-acc": "#fff"
  "blue-light-data-accent": "#3152d1"
  "blue-light-bad": "#a82945"
  "blue-light-bad-soft": "#fbe9ee"
  "utility-text": "#d6d3d1"
  "blue-action": "#4263eb"
  "blue-action-ink": "#fff"
"typography":
  "original-headline":
    "fontFamily": "Barlow Condensed, sans-serif"
    "fontSize": "30px"
  "original-figure":
    "fontFamily": "Geist Mono, monospace"
    "fontSize": "15px"
    "fontWeight": 550
  "body":
    "fontFamily": "Geist, Arial, sans-serif"
  "blue-headline":
    "fontFamily": "Geist, Arial, sans-serif"
    "fontSize": "26px"
    "fontWeight": 650
    "lineHeight": 1.2
    "letterSpacing": "-0.025em"
  "blue-team":
    "fontFamily": "Barlow Condensed, sans-serif"
    "fontSize": "17px"
    "fontWeight": 600
    "lineHeight": 1.35
  "blue-figure":
    "fontFamily": "Geist, Arial, sans-serif"
    "fontSize": "14px"
"rounded":
  "compact": "5px"
  "row": "6px"
  "blue-highlight": "7px"
  "control": "8px"
  "dialog": "12px"
"spacing":
  "tight": "6px"
  "small": "8px"
  "control": "12px"
  "row": "16px"
  "panel": "20px"
  "section": "24px"
  "wide": "32px"
"components":
  "original-odd-selected":
    "backgroundColor": "{colors.original-dark-acc}"
    "textColor": "{colors.original-dark-on-acc}"
    "rounded": "{rounded.control}"
    "padding": "8px 12px"
  "blue-odd-selected":
    "backgroundColor": "{colors.blue-dark-acc-soft}"
    "textColor": "{colors.blue-dark-acc}"
    "rounded": "{rounded.compact}"
    "padding": "10px"
  "search":
    "rounded": "{rounded.control}"
---

# Design System: Candibet

## Overview

**Creative North Star: "The Familiar Sportsbook, Two Appearances"**

Original is the default Candibet identity: near-black neutral layers, green actions, condensed sporting headlines and precise numeric data. Tournament Blue is a separate local build with graphite and cool-white surfaces, ultramarine actions, paired team highlights and aligned fixture rows. Each appearance supports dark and light themes.

Normal builds pin Original. Tournament Blue is selected only at compile time with NEXT_PUBLIC_LOCAL_BLUE=1 and served separately by scripts/local_blue.py; it has an isolated temporary export and local account data. There is no appearance selector, query activation or stored appearance preference. Only the light/dark preference persists. Portuguese content, honest source distinctions and working account, wallet and selection flows remain the product foundation. The current source of truth is the cascade globals.css → workspace.css → apex.css → variants.css; Clubhouse and Nunito are archived development history, not active design guidance.

**Key Characteristics:**
- Original defaults to green and near-black; Blue is an explicit alternate.
- Compact sports data with readable state and provenance.
- Production Original and local-only Blue, each with light/dark support.
- Local Geist, Barlow Condensed and Geist Mono assets with fixed functional roles.

## Colors

### Primary
Original uses lime green in dark mode and a deeper green in light mode for actions and selection. Tournament Blue uses fixed ultramarine filled actions in both themes, with a softer dark-theme accent and deeper light-theme accent for supporting states. The frontmatter records each appearance/theme pairing separately; runtime CSS resolves these through the shared semantic variables.

### Neutral
Original has near-black dark surfaces and warm off-white light surfaces. Blue has graphite dark surfaces and cool-white light surfaces. Ink, muted text, dividers, fields and chips change together. Original's utility strip remains dark in light mode and uses the dedicated utility text color. Blue omits that strip.

### Secondary
Error colors communicate failures; source/data accents communicate supporting data. Do not use these as arbitrary decoration.

**The Build Boundary Rule.** Normal builds are Original; Blue is compile-time local-only. Theme remains an independent persisted preference. Never reactivate Blue in production through browser state.

**The Data State Rule.** Selected, unavailable, loading and failed markets must remain distinguishable in both appearances and both themes.

## Typography

**Display Font:** Barlow Condensed, sans-serif.
**Body Font:** Geist, Arial, sans-serif.
**Label/Mono Font:** Geist Mono, monospace, for Original's numeric data.

Original's sporting headline is (30px), highlight heading (28px), feature team detail (22px), and odds figure (15px, weight 550). Blue's functional page heading is (29px, weight 650, line-height 1.2), board section heading (15px), fixture team name (19px, weight 600, line-height 1.35), odds figure (14px), and compact metadata (11–12px). On phones Blue fixture team names become (20px), with a (26px) functional page heading. The header wordmark uses Geist (27px, weight 800); its tracking is (-0.04em). These are observed roles, not a universal modular scale; form and account contexts retain their more spacious sizing.

**The Three Roles Rule.** Original uses Geist for interface text, Barlow Condensed for display and Geist Mono for figures. Mono is a numeric role, never an additional decorative voice. Blue uses Geist for functional headings, body and figures, retaining Barlow Condensed for team names.

## Layout

Original places three highlighted fixtures above a compact (176px) sports rail and market-card board, with (24px) vertical and (20px) horizontal gaps. Blue follows the decision sketch with a full-width (80px) header, a spanning (218px) left rail, (36px) content gutter, two paired-team highlights and compact table-like fixture rows; its gaps are (20px 36px). At (1200px) its rail becomes (190px) and gutters (24px). Original collapses the rail to (52px), Blue to (64px). Desktop slip layouts can reserve space beside the content.

At (1200px) the header wraps and search occupies a full row. Original switches from rail to horizontally scrolling sports tabs at (1100px); Blue switches at (1000px), where its header also wraps search into a second row. At (760px) the header simplifies, primary controls use (44px) minimum heights, Blue fixture rows stack, highlight strips scroll horizontally, and bottom navigation supplies the main destinations. Original's highlight carousel starts at (768px). Compact edge gutters and contained horizontal carousels are intentional inherited density choices; they are not a license for page overflow. Some secondary save/market actions remain smaller than 44px in the existing Blue cascade.

## Elevation & Depth

Most market surfaces use tonal layering, thin dividers and compact borders. Shadows identify floating UI: menus use (0 8px 24px #0003), the betslip (0 12px 40px #0004), and authentication (0 24px 90px #0005). Original's floating invitation retains its existing behavior and deeper shadow; Blue uses the quieter menu shadow there. These overlays do not establish a shadow treatment for fixture rows.

State transitions use (160ms) with cubic-bezier(.22, 1, .36, 1). Reduced-motion preferences suppress animation, transitions and smooth scrolling.

## Shapes

Original controls and market containers generally use (8px) corners. Blue odds use (5px), league groups (6px), and highlight cards (7px). Dialogs use (12px). Thin semantic dividers organize dense information; the geometry stays compact rather than pill-heavy.

## Components

### Buttons
Action color follows the active appearance/theme. Original selected odds fill with the accent and contrasting on-accent ink. Blue selected odds and the active rail item use the fixed ultramarine action fill with white ink; unselected odds use the chip surface. Softer theme accents support hover, focus and supplementary data. Unavailable odds retain explicit muted labels and disabled behavior. Keyboard focus uses a (2px) accent outline with (3px) offset; search has its own focus-within outline.

### Chips
Sport and filter controls distinguish active state using tonal surfaces and borders. Blue's sports rail uses a solid ultramarine active item; Original retains its green edge marker. Counts and source labels remain subordinate to teams and prices.

### Cards / Containers
Original's compact market cards sit beneath three highlights. Blue's two highlights pair home and away teams with aligned time or score; fixture rows use a shared league container and bottom dividers. Padding varies with density: Blue highlights (16px 20px), fixture rows (10px 16px), phone rows (14px 12px). Blue uses a compact live/market/date control band, with competition, favorites and reset inside an expandable Filtros panel. Repeated legacy controls and country rows are hidden; the league heading retains country context. On phones the Filtros popup aligns to the right, opens above its summary and scrolls within a viewport-bounded maximum height. Toolbar labels are inline on desktop and stacked on phones; desktop rows keep an (88px) minimum height. Casino sections retain the repaired catalog, honest image fallback and quiet separated rows.

### Inputs / Fields
Search uses the semantic field surface, thin divider border and (8px) corners. The header search has a visible label/affordance and clear action. Forms preserve their validation messages and separate authentication context; do not inherit market-row density into dialogs.

### Navigation
Normal builds compile data-design=classic and expose no Visual selector. NEXT_PUBLIC_LOCAL_BLUE=1 compiles the separate Blue shell; query parameters and casa-design cannot activate it. The existing theme control persists casa-theme and tolerates blocked storage. scripts/local_blue.py builds into /tmp/operator-blue-local and serves loopback port 8766 with isolated demo-data; it never deploys. Blue hides Original's utility strip, supplies a full-width navigation frame and aligns its footer with the content rail. Original's footer and floating invitation retain their existing behavior.

## Do's and Don'ts

### Do:
- **Do** preserve Original in normal production builds and keep Blue isolated locally.
- **Do** use the active semantic variables so every surface works in both themes.
- **Do** retain tabular figures, explicit selection state and truthful missing-data fallbacks.
- **Do** keep keyboard focus visible and honor reduced motion.

### Don't:
- **Don't** import archived Clubhouse styling or Nunito into the active cascade.
- **Don't** expose browser query, storage or selector activation for Blue in production.
- **Don't** add a fourth decorative type voice or spread Mono into body copy.
- **Don't** invent statistics, popularity, volume or promotional claims.

Not canonized: inherited compact-gutter/carousel/floating-overlay exceptions and 21 pre-existing game-cover provenance gaps remain review records, not new visual rules. Unused Clubhouse CSS and Nunito assets are superseded. No new raster assets ship with these appearances.

## Local Blue active filters (0089)

When discovery filters are active, Blue shows removable live/date/competition/favorites/search controls under its toolbar, including settings inside the closed Filtros disclosure. Limpar tudo and empty-state recovery clear live-only as well as date, competition, favorites-only and query; sport, market view, saved favorites and bet selections remain. Controls use semantic accent-soft/accent colors, 5px corners, 12px labels and 44px minimum touch heights on phones. Long labels and empty-state search terms wrap without page overflow. Original is unchanged.
