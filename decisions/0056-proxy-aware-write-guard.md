# 0056 — The write guard sees through the deploy proxy

Date: 2026-10-17
Status: accepted

## Context

Every player write (`POST /api/player`, `/api/player/login`, deposits, spins,
bets, chat, social login) passes a same-origin guard. It compared the request's
`Origin` host to the request's `Host` header, with a loopback-alias exception —
correct for the single-origin local demo (`python -m demo.server`, everything on
`127.0.0.1:8765`).

The deploy is **two origins**: the storefront runs on Vercel and proxies `/api`
to the Python backend on Render (decision 0049). From the browser the request is
same-origin (`https://<frontend>/api/...`), but by the time it reaches the
backend the `Origin` is still the frontend host while `Host` is the backend
host — so `origin.host != host`, the guard returned False, and **every write on
the Vercel site answered 403 "cross-origin writes refused"**, including login.
The local demo and the Render-hosted storefront (single origin) were unaffected,
which is why it hid.

## Decision

### 1. The decision is a pure function, tested without a socket

`demo/server.py:same_origin(origin, host, forwarded_host, extra_hosts)` is the
guard as a plain function; the handler method is a one-line call that passes
`Host`, `X-Forwarded-Host` and `FRONTEND_ORIGINS`. A bug that only shows behind
a proxy is exactly the kind that needs a unit test, and a boolean decision off
four strings does not need a running server to exercise.

### 2. A proxy is recognized two ways

- `X-Forwarded-Host` — the public host a reverse proxy names, already trusted
  elsewhere in this file (`_our_origin` uses it for game URLs).
- `FRONTEND_ORIGINS` — a comma-separated hostname/origin allowlist, for a proxy
  that does not forward the header. `render_deploy.py` and `render.yaml` set it
  to `cadiback-web.vercel.app`.

Hostnames are compared, not host:port — an `Origin` omits the default port while
`Host` may carry it, and the port was never the security boundary here. The
loopback-alias rule stays, so local dev keeps working.

### 3. It stays a same-origin guard, not a CORS opening

A foreign Origin is still refused. The allowlist names the one frontend that is
legitimately ours; it is not `Access-Control-Allow-Origin: *` and does not
weaken the guard into "any site may write".

## Alternatives considered

1. **Disable the guard on the deploy.** Rejected: it is the CSRF protection for
   a wallet; "just turn it off" trades a login bug for a real one.
2. **Make the browser send the backend's Host.** Not ours to do — the browser
   talks to the frontend; the proxy is Vercel's.
3. **Trust only `X-Forwarded-Host`.** Rejected as the sole rule: whether a given
   proxy forwards it is not guaranteed, so the explicit allowlist backs it up.

## Notes

- Suites: demo +7 (`SameOriginTest`: no-Origin, same-host, proxy-via-forwarded,
  proxy-via-allowlist, foreign-refused, loopback, `frontend_hosts` parsing);
  frame 50/50; `verify.py` 0. Decision 0056.
- Files: `demo/server.py` (`same_origin`, `frontend_hosts`, `_same_origin`),
  `scripts/render_deploy.py`, `render.yaml`, `demo/test_demo.py`.
- To take effect on the deploy, `FRONTEND_ORIGINS` must be present in the
  service's environment — `python scripts/render_deploy.py --yes` carries it.
