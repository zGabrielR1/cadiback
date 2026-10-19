# 0065 — PG's money calls ride the page's own transport

Date: 2026-10-19. Status: **shipped and live-verified on our origin**, with
no custom domain.

Follows 0040/0043/0044 (PG's document, display and trial-wallet tap) and 0064
(the live harness and the CORS measurement).

## Context

0064 proved PG settles on our books, but only when the local harness serves
the page from `api.pg-demo.com` and steers `ao` there: the client's money
calls are same-origin then, so the browser never asks the publisher's api host
for `access-control-allow-origin`. On a real deploy the document lives on our
origin (`cadiback.onrender.com`, `cadiback-web.vercel.app`), the client
rewrites `ao` to `api.<registrable domain>` (which for `onrender.com` is a host
we do not control), and every handshake dies at the splash. `0064` recorded
the only apparent fix as owning a domain at `pg.<domain>` + `api.<domain>` —
a DNS/TLS task for the owner.

## Decision

**Do not move the document to a publisher-shaped host. Move the call.**

The client builds its money URLs (`/web-api/…`, `/game-api/…`) as absolute
URLs, but they are issued by the page's own XHR/fetch. The bridge is injected
before the game bundle, so it owns those transports first. For a PG document
it rewrites any absolute `http(s)://<host>/web-api/…` or
`…/game-api/…` onto `location.origin`, keeping the path and query byte for
byte.

The request is then same-origin with the document:

- no CORS preflight and no `access-control-allow-origin` requirement;
- the `pg_session` / `proxy_*` / `wallet_token` cookies are sent normally,
  including on a cross-subdomain deploy where they carry a `Domain`;
- the server already routes root `/web-api/…` and `/game-api/…` through
  `_serve_publisher_root`, takes the api host from the session the mint named,
  resets `Origin`/`Referer` to the launcher and forwards with
  `PG_MONEY_HEADERS` (which carries `Authorization`).

`/healthcheck` deliberately stays cross-origin: it is not a money call and the
publisher answers it for any origin.

The existing `PG_PUBLIC_HOST` / `PG_AO_HOST` routing remains supported and is
now optional, not required. A custom domain still works; it is simply no
longer the only way in.

## What the live check caught

Two defects surfaced while proving the path end to end without `--host` or
`--steer`:

1. **A regression from the routing commit.** `b6189ca` inserted the routing
   helpers on top of `pg_proxy.allowed_host`'s `def` line, leaving the old
   body unreachable under `routing()`. `allowed_host` (the "this process
   minted this host" allowlist that `_serve_publisher_root` depends on) was
   gone. Restored, with its tests green again.
2. **A 500 on a legitimate round.** The tap reports a trailing feature win
   (a respin/cascade) as `stake 0, payout N`, and `settle_rgs_round` called
   `place_bet`, which refuses a positive stake requirement. A stake-less
   win is real: its stake was booked with the round that opened. New
   `Books.settle_casino_payout` posts the payout alone against the game's
   revenue account, so across the pair the books still show exactly
   `stake - total_payout`, and the tap's net stays exact.

## Verification

```
python scripts/live_spin.py --game pg:fortune-tiger \
    --start 640,624 --tap -1,717 --tap-only --press 4 --gap 3500 \
    --settle 18000 --wait 45000 --boot 10000 \
    --eval "JSON.stringify(window.__wallet_tap)"
```

No `--host`, no `--steer`: the document is on `127.0.0.1`, which PG's api host
would refuse. Observed:

- `verifySession`, `GameName/Get`, `GameInfo/Get`, `GameWallet/Get` and
  `/v4/Spin` all **200 on our origin** (previously `net::ERR_FAILED`);
- the wallet moved `500000 → 499880` across two settled rounds, one of them a
  win (`stake 200 / payout 380`), the other a loss (`stake 300 / payout 0`);
- every `/api/wallet/round` answered 200 (the stake-less win was the 500).

Suites: `frame` 50/50, `demo` 387/387, `verify.py` 0 problems, frontend build
green.

## Production notes

- The Render origin needs nothing: the document, the bridge, the money paths
  and the api poll are all on `cadiback.onrender.com`.
- The Vercel front door (server mode) now rewrites the same root paths
  (`/web-api/*`, `/game-api/*`, `/<gi>`) to the backend, so a launch from the
  Vercel storefront takes the identical path.
- The tap still polls (it does not observe the spin); two spins closer than
  its settle window can be conflated. That limit is 0064's and is unchanged.
