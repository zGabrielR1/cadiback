# SYSTEM-SHEET — Candibet / Sports desk

## Product
- Personal sports market and gated casino simulation for Portuguese-speaking followers; frequent desktop comparison and mobile score checking.
- Existing Next.js/React frontend, Python API, player sessions and transaction validation remain the functional base. Integration follows approval of the representative mockup.
- Moment of care: the selected match retains its research context beside the board; stale feed data stays readable with its age and retry action. No animated peak.
- The concept is a new frontend foundation, not a palette override on Tournament Blue. Original and Blue remain available as prior work; no publishing in this phase.

## Screen map
The current application uses React view state and overlays rather than separate URL routes. These are screen identities, not proposed backend paths.

| screen | job | layout family | shell | traffic |
|---|---|---|---|---|
| SportsHome | compare sports, fixtures and supplied prices | dense board + research desk | yes | high |
| live / favorites / search | find a scoped set and recover from empty filters | same board | yes | high |
| MarketDetail | inspect one match and all supplied markets/statistics | match masthead + two-column detail | yes | high |
| BetBuilder | research supplied data and reconcile a draft | research workspace | yes | medium |
| BetslipTray | review selection, stake, quote changes and receipt | context rail / mobile sheet | yes | high |
| AccountModal | sign in, PF/PJ signup, social login, password recovery | focused dialog | behind | high |
| CashierModal | deposit, provider minimums, Pix/crypto status, withdrawal | focused financial workspace | behind | medium |
| AccountView | profile, balances, sessions, history, exclusion | settings navigation + content | yes | medium |
| DataPortal | unlock the existing intermediate terminal boundary | concise access form | yes | low |
| CasinoHome | discover games/providers after access and login | catalog with real cover art | yes | medium |
| GameTheater | play official demos and return to catalog | full-width player | reduced | medium |
| original game panels | play crash, mines, dice, plinko, keno, wheel, roulette, slots | shared controls + game canvas | yes | medium |
| PromosView / help / chat | understand actual bonuses and get help | document / conversation | yes | low |
| AdminPanel | existing owner monitoring and controls | operational tables/forms | yes | low |
| errors / not-found | explain failure and offer recovery | small document | yes | low |

Shell: slim sports rail, white masthead with product name/navigation/search/account, central working area and contextual right rail. Current nav uses filled neutral background plus red text, never color alone. At <=1000px the sports rail becomes horizontal tabs; at <=760px context becomes an inline disclosure and the bottom bar contains main destinations. No hover-only paths.
Build order: tokens and primitive components; shell; sports board and detail; slip/login; wallet/account; terminal/catalog/player; original game panels; admin/help/errors.

## Component inventory
Budgets include size differences. Native states are marked semantically and not counted as new variants.

| component | named variants | budget | used by |
|---|---|---|---|
| button | filled action, bordered action, text action, icon, compact odds, navigation/tab, match-row trigger, score-strip trigger | 8 | all screens |
| input | text, search, stake | 3 | forms, shell, slip |
| select | standard, compact toolbar | 2 | forms, board |
| toggle | tab, filter chip | 2 | sports, wallet, settings |
| link | inline action, navigation, brand wordmark, review-toolbar | 4 | documents, shell, prototype review chrome |
| disclosure | section, compact menu | 2 | filters, settings, help |
| dialog | account, cashier, game details | 3 | focused flows |
| non-control | live/ended/upcoming badge; model/provider marker; inline error; preserved-data notice; selection row; empty message | named roles | all |

## State matrix
| component | default | hover | focus-visible | active | disabled | loading | empty | error | selected |
|---|---|---|---|---|---|---|---|---|---|
| buttons/nav/odds | declared geometry | darker surface, fine pointer only | 2px accent, 3px offset | 1px translate | native disabled + explanatory text | label remains, busy text | n/a action has no collection | adjacent message | aria-pressed/current + fill |
| inputs/selects | white field + full line | darker border | 2px accent | native | native + reason | preserve value | helpful placeholder | aria-invalid + message | native value |
| dialogs | solid surface | n/a | contained tab flow | n/a | children governed above | keep frame | show next step | preserve entered data | n/a |
| lists/markets | divider rows | row action hint | child controls | n/a | unavailable quote text | preserve dimensions | contextual copy + reset | preserve last feed + retry | selection marked |

Opacity never dims text; disabled state uses solid muted ink and dashed border. Body/placeholder contrast >=4.5:1, large >=3:1; measurements at implementation gate. No invented statistics or implied successful transactions.
State reachability: controlled browser API fixtures for loading/empty/error/stale/quote-changed during integration; mockup uses explicit example data and hash screen links. No production preview parameter.

| screen | empty wording | recovery |
|---|---|---|
| board | Nenhuma partida corresponde aos filtros. | Limpar filtros |
| favorites | Você ainda não salvou uma partida. | Ver partidas |
| research | Esta estatística ainda não foi fornecida. | Ver mercados disponíveis |
| slip | Escolha uma cotação para começar. | Ver mercados |
| history | Suas apostas aparecerão aqui. | Explorar partidas |
| sessions | Não foi possível carregar os dispositivos. | Tentar novamente |
| cashier | Selecione um método para consultar os limites. | provider selector |
| casino | Nenhum jogo encontrado para esta busca. | Limpar busca |

## Density
Desktop board targets 6–8 two-team rows visible in 900px after header/controls, with tabular odds and right-aligned scores. No sort affordance unless actual sorting exists. Long teams wrap to two lines, leagues retain full accessible names; horizontal scrolling is reserved for sports tabs or inherently wide operational tables. Match research keeps meaning when no stats exist. All informational content remains visible without animation.

## Gate
System and component/state inventory complete. Owner approved the direction on2026-10-25 and authorized production deployment with private account/wallet/betting controls hidden from guests. Integrated into the existing React frontend; release evidence and verification limits are in decision0091. The HTML mockup remains a direction artifact.
