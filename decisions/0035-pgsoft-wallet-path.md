# 0035 — PG Soft on our wallet: state and the path (assessment, not built)

Date: 2026-10-12. Status: **assessment** — no code this session. PG Soft stays
**trial play** (wallet-isolated provider demos).

## 1. Where PG Soft stands today

Two titles are listed as **provider demos** in `probes/provider-demos.json`:
`pg:fortune-tiger` (gi=126) and `pg:mahjong-ways` (gi=65), loaded from the
publisher's own trial launcher
`https://public.pg-demo.com/demo/?gi=<id>&lang=pt` (re-verified **200** this
session). They are `wallet_isolated: true` — the publisher's server holds the
money, nothing touches our books, and they are **not** served through `/g/`
(they are not `demo:` originals, and PG has no `rgs_proxy` upstream, so
`interposed_launch` returns "").

So "not implemented" means: **PG Soft boots and plays, but off our wallet.**

## 2. Why it can't run on our wallet yet — the three blockers

1. **Session mint.** The loader POSTs
   `https://public-api.pg-demo.com/web-api/operator-proxy/v2/Game/GetTrialLaunchURLHTML`
   (form-urlencoded) and gets back the game HTML; the game then boots from a
   **per-session host**, e.g.
   `https://m.<session>.com/<gi>/index.html?ot=…&l=pt&btt=2`, money on
   `https://api.<session>.com/web-api/…` (auth `session/v2/verifySession`,
   `game-proxy/v2/GameName/Get`, `game-api/<slug>/v4/GameInfo/Get` + spin).
   We would mint that session **server-side** (no vendor account needed).

2. **Dynamic host binding.** `<session>` is a random-letter domain, so the
   static allowlists (`provider_demos.DEMO_HOSTS`, `game_proxy.ALLOWED_SUFFIXES`)
   can never cover it — as 0029 noted. The proxy needs a **per-session dynamic
   allowlist**: bind the exact `m.<session>.com` / `api.<session>.com` host
   strings minted for this session and accept only those, instead of a suffix
   rule. This is the one genuinely new mechanism PG needs that Hacksaw did not.

3. **Money tap.** Mirror the `game-api` spin request/response to our books —
   parse the stake/win, swap the balance (`rewrite_balance`), swap our token out
   of the outbound call and the publisher's back in (as `rgs_proxy` does for
   Hacksaw), and hold the spin when the saldo cannot cover it (the R$0 gate).

## 3. Options

- **(A) Full wallet integration** — mint session + dynamic host binding +
  game-api mirror + gate. **Hacksaw-sized** (decision 0025). Inherently
  brittle: the previous PG hosts (`m/static.pgsoft-games.com`) died globally,
  so this rides on hosts the publisher can rotate without notice.
- **(B) Leave as trial play** — status quo. Zero risk; no wallet. **Chosen.**
- **(C) Drop PG** — not warranted; the trial rows are harmless and playable.

## 4. If (A) is picked up — first steps

1. **Live-probe the mint** (like `probes/` does for other providers): POST the
   launcher form and record the returned hosted session, the `ot=` token, and
   the exact `game-api` request/response shapes for one spin. Capture to
   `probes/pg-soft.json`.
2. **`pg_proxy`** module, mirroring `rgs_proxy`: mint the session, hold the
   dynamic host binding in a per-session dict (cookie-bound), forward and
   mirror money calls, and gate at R$0.
3. Register `pg:<slug>` as **launchable** against our wallet (they are currently
   forced `launchable: False` in `provider_demos._accept`), wire `interposed`
   or page-proxy launch, and add a wallet test that a spin debits/settles on
   `frame` books.

Recommendation: **keep (B)**; treat the above as a ready-to-work task when PG
is worth the brittleness.
