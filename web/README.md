# web — Next.js storefront (the real front-end)

React 19 + Next 16 App Router, static-exported. The Python server in
`demo/server.py` serves `web/out` when it exists and falls back to the
zero-build `demo/index.html` when it does not — same API either way, so the
contract is frozen and both paths stay runnable.

## Build / run

```bash
cd web
npm ci                 # reproducible install from package-lock.json
                       # (use npm install only to add/change deps)
npm run build          # -> web/out (static export)

cd ..
python -m demo.server  # serves the export at http://127.0.0.1:8765
```

Dev loop with hot reload (optional, separate port):

```bash
cd web && npm run dev  # http://127.0.0.1:3000
```

`next.config.js` proxies `/api/*` to the Python server on :8765. Without it,
`npm run dev` returns Next's 404 HTML for every API call and the browser
throws `JSON.parse: unexpected character at line 1 column 1` when creating a
user. Verified: POST /api/player through :3000 now returns JSON.

## Official games (free play)

Official provider titles are **embedded in a theater player**, not linked
out. `probes/provider-demos.json` stores one `demo_url` per title (publisher's
own free-play host, https + host allowlist enforced by
`demo/provider_demos.py`), and `page.jsx` renders it in a fullscreen-capable
iframe with reload, new-tab and quick-switcher controls. Every row ships
`wallet_isolated: true` / `launchable: false` — no stake ever touches our
books, no game files are rehosted (decision 0006).

Providers that refuse framing (`X-Frame-Options`, bot protection) simply
fail to render inside the iframe; the "↗ Nova Aba" control is the escape
hatch. These are the real games, no contract needed, no money moves through
our wallet — development/demo content, not a certified launch catalogue.

## Quality control

`python scripts/verify.py` (repo root) covers this app:

- required files: `page.jsx`, `layout.jsx`, `error.jsx`, `globals.css`,
  `components/CasinoHome.jsx`, `components/SportsHome.jsx`, `lib/api.js`,
  `next.config.js`, `package.json`;
- the export must exist and every `/_next/…` asset `web/out/index.html`
  references must exist in `web/out` (catches a half-built export);
- freshness: any `web/app`, `web/lib` or `web/public` file newer than
  `web/out/index.html` fails the check — rebuild after every source edit
  (`cd web && npm run build`), which is AGENTS workflow step 5;
- fragment markers (`TODO|FIXME|XXX|HACK`) are refused in web sources the
  same way they are refused in Python sources.

There is no JS test runner yet (`npm run build` is the compile check); the
Python suites cover the API contract this app talks to.

## Layout

- `app/layout.jsx` — html shell, `data-theme="dark"` default.
- `app/page.jsx` — the storefront shell: sticky header (nav, search, balance,
  theme toggle, Depositar/Entrar), cashier modal (depositar/sacar), account
  panel (profile, history, risk, health), sport/promos views, mobile bottom
  nav, compliance footer.
- `app/components/CasinoHome.jsx` — the casino games page, laid out to match
  Superbet's `/jogos` section order: hero banners → quick links + provider
  chips → category sidebar + search → Destaques → Todos os Jogos grid →
  Quentes e frios → Jackpot → Super Odds → Torneios → Notícias. Original
  components and copy; the information architecture is the match, not their
  code or assets. Recentes/Favoritos are tabs in the same grid (localStorage),
  and every card opens a detail modal before launch (favoritar + Jogar Agora).
- `app/components/SportsHome.jsx` — league chips over the fixture list,
  inline markets/prices, live-only filter, read-only feed provenance; picks
  flow into the shared betslip state owned by `page.jsx`.
- `app/components/AdminPanel.jsx` — painel administrativo, **gated by a
  real login** (default `admin`/`admin`; Bearer token in
  `localStorage["casa-admin"]`, sent by `lib/api.js` on every request).
  Login door + logout + own-password change + user credential
  management (create / reset / remove, admin role only), then the
  dashboard: KPI grid, realized-vs-model RTP bars, 7-day volume chart,
  top winners / biggest wins, risk counts — all from `GET /api/admin`,
  derived server-side from the ledger/books/players stores. The header
  "Painel" button renders only for a logged-in admin; the owner reaches
  the login door with **Ctrl+Shift+A**.
- `app/globals.css` — dark theme with neon-green accent + gold paytable,
  light theme via `[data-theme="light"]`, persisted in localStorage.
- `lib/api.js` — the single fetch helper; all views share it.

## Notes

- Client-side rendering: the page hydrates then calls `/api/*` on the same
  origin, so no CORS and no server component data plumbing.
- Official content stays gated: `catalog.vendor` titles are listed but
  never launchable until real BR certificates are registered.
- Node/npm live at `C:\Program Files\nodejs` (node 24.21.0, npm 11.19.0).
  If `node` is not on PATH in your shell, use the full path or add it.
  PowerShell's default execution policy blocks the `.ps1` shims, so call
  `npm.cmd` (or run npm from cmd) rather than bare `npm`.