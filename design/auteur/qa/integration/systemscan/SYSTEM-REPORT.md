# SYSTEM-REPORT — 1 route(s), 2026-10-25

The system as **painted**, not as documented. A token in the stylesheet that never renders is
not part of the system; a one-off inline style is. Read this against `design/DESIGN.md` — every
number below that DESIGN.md does not account for is drift.

**Look at `components.png`** — one tile per distinct rendered control variant. Two tiles that look the same to you but appear separately are the drift.

## Controls

| kind | distinct variants | budget | total instances |
|---|---|---|---|
| link | **1** | 4 | 1 |
| button | **7** | 8 | 12 |
| input | **1** | 3 | 1 |

### link
- ×1 on 1 route(s) — "Ir para as partidas" — `lab(44.6614 62.7587 46.643) | lab(100 0 0) | lab(100 0 0) | 0b | 8r | 13/600 | 10x14 | noshadow`

### button
- ×1 on 1 route(s) — "candi
bet" — `rgba(0, 0, 0, 0) | lab(9.47247 -0.459656 -4.40383) | lab(9.47247 -0.459656 -4.40383) | 0b | 4r | 27/800 | 0x0 | noshadow`
- ×4 on 1 route(s) — "Ao vivo" — `rgba(0, 0, 0, 0) | lab(9.47247 -0.459656 -4.40383) | lab(9.47247 -0.459656 -4.40383) | 0b | 4r | 15/600 | 12x0 | noshadow`
- ×1 on 1 route(s) — "submit" — `rgba(0, 0, 0, 0) | lab(9.47247 -0.459656 -4.40383) | lab(9.47247 -0.459656 -4.40383) | 0b | 4r | 13/600 | 9x12 | noshadow`
- ×1 on 1 route(s) — "Entrar" — `lab(44.6614 62.7587 46.643) | lab(100 0 0) | lab(100 0 0) | 0b | 4r | 14/650 | 11x20 | noshadow`
- ×1 on 1 route(s) — "‹" — `rgba(0, 0, 0, 0) | lab(38.4664 -0.680119 -5.55185) | lab(38.4664 -0.680119 -5.55185) | 0b | 4r | 20/600 | 0x0 | noshadow`
- ×1 on 1 route(s) — "Tentar novamente" — `lab(100 0 0) | lab(9.47247 -0.459656 -4.40383) | lab(84.9011 -0.317544 -2.24477) | 1b | 4r | 14/600 | 10x16 | noshadow`
- ×3 on 1 route(s) — "Esportes" — `rgba(0, 0, 0, 0) | lab(9.47247 -0.459656 -4.40383) | lab(9.47247 -0.459656 -4.40383) | 0b | 4r | 13/600 | 0x0 | noshadow`
- *states (not counted as variants): current ×1*

### input
- ×1 on 1 route(s) — "text" — `rgba(0, 0, 0, 0) | lab(9.47247 -0.459656 -4.40383) | lab(9.47247 -0.459656 -4.40383) | 0b | 0r | 14/400 | 0x0 | noshadow`

> States — disabled, current, and controls inside a row carrying a `data-state` — are
> excluded from the variant budget. A disabled button paints differently on purpose; a
> product that has no disabled state at all should not score better than one that does.

## Tokens as rendered

**Colour** (5 distinct)
- `lab(38.4664 -0.680119 -5.55185)` — 15× on 1 route(s)
- `lab(9.47247 -0.459656 -4.40383)` — 12× on 1 route(s)
- `lab(100 0 0)` — 7× on 1 route(s)
- `lab(44.6614 62.7587 46.643)` — 6× on 1 route(s)
- `lab(97.0939 -0.108689 -0.749958)` — 2× on 1 route(s)

**Type step** (15 distinct)
- `13px/600/Source Sans 3` — 6× on 1 route(s)
- `13px/700/Source Sans 3` — 5× on 1 route(s)
- `15px/600/Source Sans 3` — 4× on 1 route(s)
- `13px/400/Source Sans 3` — 3× on 1 route(s)
- `11px/400/Source Sans 3` — 2× on 1 route(s)
- `12px/400/Source Sans 3` — 2× on 1 route(s)
- `14px/600/Source Sans 3` — 2× on 1 route(s)
- `27px/800/Archivo` — 1× on 1 route(s)
- `14px/650/Source Sans 3` — 1× on 1 route(s)
- `39px/750/Archivo` — 1× on 1 route(s)
- …and 5 more

**Radius** (4 distinct)
- `4px` — 14× on 1 route(s)
- `5px` — 2× on 1 route(s)
- `8px` — 1× on 1 route(s)
- `50px` — 1× on 1 route(s)

**Shadow** (0 distinct)

## Per route

| route | landmarks | h1 | focusable | console errors |
|---|---|---|---|---|
| http://127.0.0.1:8765 | header,nav,main,footer,aside | 1 | 15 | 3 |

## WARN
- button variant used exactly once ("candi
bet") — either promote it into the system or delete it: rgba(0, 0, 0, 0) | lab(9.47247 -0.459656 -4.40383) | lab(9.47247 -0.459656 -4.40383) | 0b | 4r | 27/800 | 0x0 | noshadow
- button variant used exactly once ("submit") — either promote it into the system or delete it: rgba(0, 0, 0, 0) | lab(9.47247 -0.459656 -4.40383) | lab(9.47247 -0.459656 -4.40383) | 0b | 4r | 13/600 | 9x12 | noshadow
- button variant used exactly once ("Entrar") — either promote it into the system or delete it: lab(44.6614 62.7587 46.643) | lab(100 0 0) | lab(100 0 0) | 0b | 4r | 14/650 | 11x20 | noshadow
- button variant used exactly once ("‹") — either promote it into the system or delete it: rgba(0, 0, 0, 0) | lab(38.4664 -0.680119 -5.55185) | lab(38.4664 -0.680119 -5.55185) | 0b | 4r | 20/600 | 0x0 | noshadow
- button variant used exactly once ("Tentar novamente") — either promote it into the system or delete it: lab(100 0 0) | lab(9.47247 -0.459656 -4.40383) | lab(84.9011 -0.317544 -2.24477) | 1b | 4r | 14/600 | 10x16 | noshadow
- 15 distinct type steps across the product — a scale nobody can hold in their head is not a scale
- no disabled control appeared on any route — the disabled state is probably undesigned, not absent
