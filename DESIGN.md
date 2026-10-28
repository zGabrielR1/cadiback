---
name: "Candibet — Sports desk"
description: "Owner-approved Auteur frontend, with private financial controls after login."
colors:
  paper: "oklch(.975 .002 260)"
  card: "oklch(1 0 0)"
  ink: "oklch(.22 .012 260)"
  muted: "oklch(.47 .015 260)"
  line: "oklch(.87 .006 260)"
  accent: "oklch(.54 .20 28)"
  accent-soft: "oklch(.965 .015 28)"
  on-accent: "oklch(1 0 0)"
  dark-paper: "oklch(.19 .009 260)"
  dark-card: "oklch(.235 .009 260)"
  dark-ink: "oklch(.96 .003 260)"
  dark-muted: "oklch(.76 .009 260)"
  dark-accent: "oklch(.76 .14 28)"
typography:
  display:
    fontFamily: "Archivo, sans-serif"
    fontSize: "clamp(28px, 2.7vw, 40px)"
    fontWeight: 750
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  body:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "16px"
    lineHeight: 1.5
  control:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "14px"
    fontWeight: 600
rounded:
  account-panel: "6px"
  control: "4px"
  panel: "5px"
  dialog: "8px"
spacing:
  small: "8px"
  control: "12px"
  row: "16px"
  section: "24px"
  wide: "32px"
components:
  primary-button:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.control}"
    padding: "11px 20px"
---

# Design System: Candibet Sports desk

## Overview

**Creative North Star: "The daylight sports desk"**

The owner approved the Auteur direction on2026-10-25 and authorized production deployment after guest account/wallet/betting navigation was hidden. Normal builds use Sports desk; its design layer reuses the current React components and existing API/session/payment contracts. The detailed component contract is design/DESIGN.md; the earlier Original/Blue system is archived in design/ORIGINAL-AND-BLUE.md.

**Key Characteristics:**
- Daylight silver and white with restrained vermilion actions.
- Real score strip, aligned fixture rows and contextual match research.
- One typography and state system across account, wallet, login and terminal.
- Sports/research public surface; private controls appear after validated login.

## Colors

Use semantic variables from web/app/auteur.css. Light is the default; stored light/dark preference remains. Dark uses charcoal and a brighter readable vermilion while preserving the same roles. State is communicated by words and aria attributes as well as color.

**The State Rule.** Missing data stays missing, failed refresh keeps the last successful board, and selection does not imply a confirmed transaction.

## Typography

Archivo supplies display/match headings; Source Sans3 supplies body, forms, labels and tabular figures. Local woff2 assets and OFL texts ship together. No third decorative face. Source CSS records the role-specific sizes; use16px body,14px controls and11–13px supporting metadata without shrinking forms to market density.

## Layout

Sports use an asymmetric rail/board/context layout, horizontal tabs on tablets and stacked rows/context on phones. Account uses section navigation and readable balance type. Cashier uses a form plus explanatory context; mobile stacks that context below the form. Floating betslip remains authenticated and reserves its desktop lane. Existing game cover art, game canvases and admin tables use shared theme variables.

## Elevation & Depth

Flat tonal surfaces and one-pixel structural lines organize data. Shadows belong to floating menus, slips and dialogs. Buttons use120ms ease-out; reduced motion removes displacement. No new scroll choreography or media effects.

## Shapes

Compact controls and panels use the documented radii. No decorative tinted icon squares, gradients on text or glowing financial figures. Every keyboard target has a visible accent outline; touch actions keep comfortable heights.

## Components

The working sources are Header, BottomNav, SportsHome, MarketDetail, AccountView, CashierModal, AccountModal and the existing terminal/game/admin components. Conditional rendering hides account/wallet/promotions/casino/balance/slip controls from signed-out visitors. Entrar remains a neutral door. Logout clears selections and private views. Public prices open research. All existing authenticated submission/review/provider minimums and session validation remain.

### Regression repair (0092)
Signed-in casino and catalog access no longer require the optional data-portal code. Criar Aposta is a direct member header/mobile action. The logo is a real root navigation link. Discovery shows five primary sports, an explicit others control and eight initial fixtures. Empty/slow/failed feed states offer honest explanations and recovery; retry cancels the previous request.

Account uses an identity header and icon tabs for profile, devices, history and protection. Tooltips and accessible names label icon actions; keep consequential confirmation copy. Only the active tab is visible. The betslip is hidden over account/casino while preserving selections, and it supports pointer/keyboard width and height adjustment. Search expands on focus and supports desktop width adjustment. Viewport bounds and dynamic header height constrain floating panels. Native resizing is a working control, not decorative animation.

## Do's and Don'ts

### Do:
- Preserve the approved Sports desk composition and new font roles.
- Verify both guest and authenticated states at desktop and mobile widths.
- Use actual feed/provider values and keep missing/stale states explicit.

### Don't:
- Expose private financial/account navigation to guests.
- Ship mockup fixtures, sample balances or review-only controls.
- Change server transaction semantics for presentation changes.
