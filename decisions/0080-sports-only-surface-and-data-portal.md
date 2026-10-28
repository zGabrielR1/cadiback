# 0080 — Sports-only public surface and data portal

The public storefront now presents itself as a sports odds site and nothing
else. Casino entries are gone from the header, the mobile bottom navigation,
the footer and the document metadata; the promos FAQ and the account history
speak only about markets, bets and settlements. The casino catalog is no longer
requested on boot: an anonymous or locked visit makes no request for game rows,
so the network footprint of the public surface matches what it shows.

The full terminal sits behind a neutral intermediate surface, "Central de
dados" (`DataPortal`), reachable through the discreet **Dados** doors in the top
bar, the footer and the mobile bottom navigation, or directly at `/#dados`.
The page reads as an operator data surface — feed origin, coverage,
repricing — and asks for an operational code. A correct code unlocks the
session (kept in `sessionStorage`), reveals the terminal navigation and lets an
authenticated player enter the casino; an unauthenticated visitor is sent to the
existing login with a neutral notice. "Encerrar acesso" clears the unlock and
returns to sports. The code defaults to `feed-seguro` and can be overridden at
build time with `NEXT_PUBLIC_DATA_ACCESS_CODE`.

While locked, the account history filters to sports bets and the casino views,
game theater and details are unreachable. Once unlocked, the existing signed-in
casino behaviour (decision 0073) is unchanged, including its login requirement.

This is a UI/obscurity boundary, not a security control. The app is a static
export, so the comparison and the code itself ship in the bundle, and the
backend keeps its current access rules. A real access boundary would have to
be enforced server-side.

Validation: production export build; frontend Node tests 19/19 including three
new access-gate tests; `verify.py` 0 problems; `frame` 50/50; `demo` 426/426.
A Playwright pass at 1440 and 390 ran 26 checks with no page errors: the public
header/footer/mobile nav carry no casino entry, the top-bar door opens the
portal, a wrong code is refused, the correct code unlocks, `#dados` opens the
portal directly, the unlock survives a reload, and the terminal still asks a
guest to log in. The exported HTML contains no casino wording.

Published to production on Vercel: deployment
`https://cadiback-oh6j1r5ac-memy2.vercel.app`, aliased to
`https://cadiback-web.vercel.app`. Live checks: public page 200 with the new
"Cotações Esportivas" title and zero casino mentions in the HTML; the gate
is present in a served chunk; `/api/health` ok; `/api/sports` 320 fixtures from
Flashscore; both social providers listed; protected player route 401. The
backend was not redeployed (frontend-only change).
