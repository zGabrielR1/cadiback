# SYSTEM-REPORT — 8 route(s), 2026-10-25

The system as **painted**, not as documented. A token in the stylesheet that never renders is
not part of the system; a one-off inline style is. Read this against `design/DESIGN.md` — every
number below that DESIGN.md does not account for is drift.

**Look at `components.png`** — one tile per distinct rendered control variant. Two tiles that look the same to you but appear separately are the drift.

## Controls

| kind | distinct variants | budget | total instances |
|---|---|---|---|
| link | **4** | 4 | 16 |
| button | **8** | 8 | 50 |
| input | **3** | 3 | 4 |
| select | **2** | 2 | 2 |

### link
- ×4 on 1 route(s) — "Esportes" — `rgba(0, 0, 0, 0) | oklch(1 0 0) | oklch(1 0 0) | 0b | 0r | 14/600 | 0x0 | noshadow`
- ×1 on 1 route(s) — "candi
bet" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 27/800 | 0x0 | noshadow`
- ×7 on 1 route(s) — "Central de dados
↗" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 14/600 | 0x0 | noshadow`
- ×4 on 1 route(s) — "Carteira" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 4r | 14/600 | 10x12 | noshadow`
- *states (not counted as variants): current ×11*

### button
- ×7 on 1 route(s) — "Ao vivo" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 14/600 | 0x0 | noshadow`
- ×6 on 1 route(s) — "submit" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 4r | 14/400 | 0x0 | noshadow`
- ×2 on 1 route(s) — "Entrar
↗" — `oklch(0.54 0.2 28) | oklch(1 0 0) | rgba(0, 0, 0, 0) | 1b | 4r | 14/650 | 11x18 | noshadow`
- ×9 on 1 route(s) — "Basquete
8" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 4r | 14/600 | 10x12 | noshadow`
- ×3 on 1 route(s) — "68′ Brasileirão
Flamengo" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 13/400 | 0x0 | noshadow`
- ×5 on 1 route(s) — "Flamengo
1
Palmeiras
0" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 15/600 | 0x0 | noshadow`
- ×15 on 1 route(s) — "2.10" — `oklch(1 0 0) | oklch(0.22 0.012 260) | oklch(0.87 0.006 260) | 1b | 4r | 14/400 | 12x8 | noshadow`
- ×3 on 1 route(s) — "Sair da conta de exemplo" — `oklch(1 0 0) | oklch(0.22 0.012 260) | oklch(0.87 0.006 260) | 1b | 4r | 14/650 | 11x18 | noshadow`
- *states (not counted as variants): current ×10 · disabled ×2*

### input
- ×1 on 1 route(s) — "search" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 14/400 | 0x0 | noshadow`
- ×1 on 1 route(s) — "number" — `rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 14/600 | 0x0 | noshadow`
- ×2 on 1 route(s) — "password" — `oklch(1 0 0) | oklch(0.22 0.012 260) | oklch(0.87 0.006 260) | 1b | 4r | 14/600 | 12x12 | noshadow`

### select
- ×1 on 1 route(s) — "Resultado da partida
Tot" — `oklch(1 0 0) | oklch(0.22 0.012 260) | oklch(0.87 0.006 260) | 1b | 4r | 13/400 | 8x8 | noshadow`
- ×1 on 1 route(s) — "Pix
Criptomoeda" — `oklch(1 0 0) | oklch(0.22 0.012 260) | oklch(0.87 0.006 260) | 1b | 4r | 13/600 | 12x12 | noshadow`

> States — disabled, current, and controls inside a row carrying a `data-state` — are
> excluded from the variant budget. A disabled button paints differently on purpose; a
> product that has no disabled state at all should not score better than one that does.

## Tokens as rendered

**Colour** (10 distinct)
- `oklch(0.22 0.012 260)` — 57× on 1 route(s)
- `oklch(0.47 0.015 260)` — 31× on 1 route(s)
- `oklch(1 0 0)` — 26× on 1 route(s)
- `oklch(0.54 0.2 28)` — 10× on 1 route(s)
- `oklch(0.975 0.002 260)` — 2× on 1 route(s)
- `oklch(0.965 0.015 28)` — 2× on 1 route(s)
- `oklch(0.945 0.004 260)` — 2× on 1 route(s)
- `oklch(0.87 0.006 260)` — 1× on 1 route(s)
- `oklch(0.9 0.012 200)` — 1× on 1 route(s)
- `oklch(0.87 0.012 28)` — 1× on 1 route(s)

**Type step** (29 distinct)
- `14px/600/Source Sans 3` — 20× on 1 route(s)
- `14px/650/Source Sans 3` — 16× on 1 route(s)
- `12px/600/Source Sans 3` — 12× on 1 route(s)
- `14px/700/Archivo` — 12× on 1 route(s)
- `12px/400/Source Sans 3` — 8× on 1 route(s)
- `11px/400/Source Sans 3` — 7× on 1 route(s)
- `14px/400/Source Sans 3` — 7× on 1 route(s)
- `13px/900/Source Sans 3` — 6× on 1 route(s)
- `11px/600/Source Sans 3` — 5× on 1 route(s)
- `13px/400/Source Sans 3` — 5× on 1 route(s)
- …and 19 more

**Radius** (4 distinct)
- `4px` — 35× on 1 route(s)
- `5px` — 4× on 1 route(s)
- `50px` — 3× on 1 route(s)
- `3px` — 2× on 1 route(s)

**Shadow** (0 distinct)

## Per route

| route | landmarks | h1 | focusable | console errors |
|---|---|---|---|---|
| http://127.0.0.1:8770/mockup.html#sports | header,nav,main,footer,aside | 8 | 62 | 0 |
| http://127.0.0.1:8770/mockup.html#account | header,nav,main,footer,aside | 8 | 32 | 0 |
| http://127.0.0.1:8770/mockup.html#wallet | header,nav,main,footer,aside | 8 | 33 | 0 |
| http://127.0.0.1:8770/mockup.html#terminal | header,nav,main,footer,aside | 8 | 27 | 0 |
| http://127.0.0.1:8770/mockup.html#detail | header,nav,main,footer,aside | 8 | 30 | 0 |
| http://127.0.0.1:8770/mockup.html#portal | header,nav,main,footer,aside | 8 | 25 | 0 |
| http://127.0.0.1:8770/mockup.html#help | header,nav,main,footer,aside | 8 | 23 | 0 |
| http://127.0.0.1:8770/mockup.html#game | header,nav,main,footer,aside | 8 | 27 | 0 |

## WARN
- link variant used exactly once ("candi
bet") — either promote it into the system or delete it: rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 27/800 | 0x0 | noshadow
- input variant used exactly once ("search") — either promote it into the system or delete it: rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 14/400 | 0x0 | noshadow
- input variant used exactly once ("number") — either promote it into the system or delete it: rgba(0, 0, 0, 0) | oklch(0.22 0.012 260) | oklch(0.22 0.012 260) | 0b | 0r | 14/600 | 0x0 | noshadow
- select variant used exactly once ("Resultado da partida
Tot") — either promote it into the system or delete it: oklch(1 0 0) | oklch(0.22 0.012 260) | oklch(0.87 0.006 260) | 1b | 4r | 13/400 | 8x8 | noshadow
- select variant used exactly once ("Pix
Criptomoeda") — either promote it into the system or delete it: oklch(1 0 0) | oklch(0.22 0.012 260) | oklch(0.87 0.006 260) | 1b | 4r | 13/600 | 12x12 | noshadow
- 29 distinct type steps across the product — a scale nobody can hold in their head is not a scale
