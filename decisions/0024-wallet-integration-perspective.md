# 0024 — provider wallet sync, a different perspective

Date: 2026-10-12. Status: proposal (needs the owner's direction pick). Newest
file wins on conflict. Companion to 0022 (the current, partly-built approach).

## Why we kept going in circles

Every session re-derived the same wall and then added *more generic
machinery* to climb it: a page proxy, URL rewriting, an injected bridge, a
per-provider `MONEY_PATHS` list. Each new vendor invalidated an assumption
the previous machinery was built on (Hacksaw is HTTP+JSON and takes an
`env=`; Pragmatic Play is a Unity client with the RGS host baked in; Spribe
and Play'n GO speak WebSocket). **One generic interposer cannot satisfy
transports that disagree.** That is the circle.

The recon (`research/game-recon/out/*/network.json`) shows it plainly: these
are not one integration, they are **six different ones**.

| Vendor | Launcher surface | Money transport | Client can be pointed at us? |
|--------|------------------|-----------------|------------------------------|
| Hacksaw | `index.html?…&env=<rgs>` | HTTP+JSON `/api/play/*` | **yes, natively** (the `env=` param) |
| Pragmatic Play | `gs2c/openGame.do` → `mgckey=…~SESSION@<uuid>` | HTTP form `gs2c/*.do` | no — host is baked into the launcher/config |
| Play'n GO | `ContainerLauncher?…&practice=1&demo=2` | WebSocket → `ascflyp.playngonetwork.com` (+ HTTP config) | no — needs a WS proxy |
| Spribe | `/launch/<game>` (SmartFoxServer) | WebSocket (SFS) | no — needs a WS proxy |
| PG Soft | static CDN | — | blocked (DNS) |
| Evolution | live dealer | WS/HTTP | no — needs a WS proxy |

## The different perspective

**Invert the problem. Model each vendor as a *wallet protocol contract*, and
shrink the client-side surface to the smallest thing the vendor allows.**

Today the design is "one interposer that must fit everyone." The reframe is:

1. **Our backend implements the vendor's operator-wallet contract** — the
   documented, vendor-shaped method set (`balance`/`bet`/`win`/`endround`/
   `rollback`, or `/api/play/*`), not a reverse-engineered client. These are
   small and per-*vendor*, so a title added from an integrated vendor is free.
2. **The client-side surface is whatever the vendor permits, smallest first:**
   - *Config-pointing* (best): the vendor names its RGS from a config value
     we control — Hacksaw's `env=`. **Zero page bytes proxied.**
   - *Config-resource rewrite*: the vendor bakes the RGS host into a config
     resource it fetches over HTTP (PP: `customizations.info` /
     `client/game.json` / `bootstrap.js?key=`). Serve the **launcher document
     plus that one resource** from our origin and rewrite the host there.
     Assets keep coming straight from the CDN (it already sends `ACAO: *`),
     so the Unity importer never sees a rewritten byte — the thing that
     stalls it today.
   - *WebSocket proxy* (last): vendors whose game protocol is a socket
     (Spribe SFS, Play'n GO). Terminate the socket and translate to the
     wallet contract. This is the missing mechanism, not a bigger page proxy.
3. **Where the vendor exposes no wallet contract at all (free play only),
   stay wallet-isolated** — which is the honest state of a demo — and say so
   in the UI. Don't fake a sync that has no counterpart.

The load-bearing insight: **our pain is proportional to how many page bytes we
proxy.** Route 1 proxies zero; route 2 today proxies everything (hence the
Unity rabbit hole). The step change is to shrink route 2 to *launcher +
one config resource*, and to stop pretending route 3 is route 2.

## What that changes concretely

- Hacksaw — already the model: 0 bytes proxied, wallet moves both ways. Keep.
- Pragmatic Play — stop byte-patching `build.js`. Proxy only the launcher and
  the config resource that names the RGS host; let the CDN serve the client.
  The Unity stall disappears because we stop touching its bundles.
- Spribe / Play'n GO — build **one** WebSocket proxy and translate each
  vendor's socket frames to the wallet contract. This is where the next real
  work is; it is not reachable by extending the page proxy.
- The lobby labels each title by its real capability: *saldo da casa*
  (wallet-settled) vs *demonstração* (wallet-isolated free play).

## Options for the owner

1. **Do the WebSocket proxy** (Spribe first — Aviator is the marquee crash
   title) and translate it to the wallet contract. New mechanism, unlocks a
   whole vendor class. *(Recommended: it is the missing piece, not a retry.)*
2. **Shrink Pragmatic Play to launcher+config** — kills the Unity stall by
   not proxying assets; aims the effort at the single config resource.
3. **Both, staged**: (2) to fix the one in-flight vendor, then (1) for the
   WS class.
4. **Stop at the honest line**: integrate only vendors whose contract works
   (Hacksaw today), label the rest *demonstração*, and stop spending on the
   rest of the class.
