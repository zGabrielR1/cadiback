# Reference IA — captured from the BR operators (2026-10-04)

What we took from the reference sites is the **information architecture**: the
order of sections, the navigation, the component vocabulary. What we did **not**
take is their code, CSS, images, fonts, or copy — our components are ours.

## Capture result (from this host)

| Site | Result | What it gave |
|------|--------|--------------|
| `superbet.bet.br` | 200, ~6.7 KB | JS bootstrap shell only (`<div id="app">`); no server-rendered markup to read |
| `www.betano.bet.br` | 200, ~273 KB | full server-rendered `initial_state`: header, main menu, home components, sports tree, bottom nav |
| `www.novibet.bet.br` | 403 | bot-blocked from this host |
| `www.bet365.bet.br` | 403 | bot-blocked from this host |

Betano is the only one of the four that renders its IA server-side; it is the
reference we could read. Superbet and Bet365 hydrate entirely client-side, so a
single GET yields a shell.

## Betano IA (facts, from its own `initial_state`)

- **Header**: logo, search (`Procure por jogos, competições, mercados…`), a
  unified offers menu, a help link.
- **Main menu**: `APOSTAS ESPORTIVAS` · `APOSTAS AO VIVO` · `CASSINO` ·
  `CASSINO AO VIVO` · `JOGOS CRASH`.
- **Sports hub**: popular leagues, `Próximos jogos` / `Ao Vivo` / `Esportes`
  tabs, per-sport competition groups.
- **Home components**: top events, acca cards, star players, cross-sell
  products, smart picks, upcoming coupons.
- **Casino hub**: `CASSINO` · `CASSINO AO VIVO` · `JOGOS CRASH`.
- **Bottom nav**: `Início` · `Ao Vivo` · `Esportes` · `Apostas`.

## What we mirrored (own code)

- `web/app/components/SportsHome.jsx` — popular-league chips over an event list,
  each event carrying its markets and prices inline (the operator order).
- `web/app/page.jsx` — sports-first default view; top menu
  `Esportes · Ao Vivo · Cassino · Cassino ao Vivo · Crash`; bottom nav
  `Início · Ao Vivo · Cassino · Apostas · Caixa`; search placeholder matching the
  operator wording.
- `web/app/components/CasinoHome.jsx` — casino hub with the publisher-hosted
  demo lobby (see `probes/provider-demos.json`).

## Boundary

Reference sites were read for **layout and navigation only**. No HTML, CSS,
JavaScript, image, font, or copy from any reference site was copied into this
repo. `verify.py` still reports zero problems and no third-party asset is
vendored here.
