# 0006 — official casino content: publisher-hosted demos, never a re-upload

Date: 2026-10-04. Status: decided. Newest file wins on conflict.

## Decision

The lobby's official content is the **publishers' own free-play demos**, served
from the publishers' own hosts (Pragmatic Play, PG Soft, Hacksaw Gaming, Play'n GO,
Evolution). We store only **facts** (title, provider, demo URL) and open the
publisher's page. We do not rehost, mirror, proxy, or copy their game code,
artwork, or files.

## Why

1. **We do not own it.** The game bytes, RNG, and artwork belong to the publisher.
   Copying them into our repo is piracy regardless of any "authorization" claim,
   and it is not a basis for a regulated operation.
2. **Security.** A game bundle pulled from an unofficial source is the classic
   malware delivery vector, and it can never be certified — so it can never be
   launched for real money anyway.
3. **The cert gate already forbids it.** No BR-issued per-title certificate, no
   real-money launch (Portaria 1207/2024). A re-upload cannot obtain that
   certificate.

## Implementation

- `probes/provider-demos.json` — the captured facts, one row per title, with
  per-row provenance and verification notes.
- `demo/provider_demos.py` — loader with two hard rules: **https only**, and a
  **host allowlist** of the publishers' own demo hosts. A row that fails either
  is dropped before it can reach the lobby.
- `/api/catalog` exposes the block as `provider_demos`; every row is
  `wallet_isolated: true` and `launchable: false`, so no stake or payout can
  route through it.

## What this rules out

- Pulling game files from unofficial sources (piracy + malware + uncertifiable).
- Byte-copying a publisher's or a reference operator's code, CSS, or assets.
- Hosting "major publisher games" ourselves. If a title cannot be shown from the
  publisher's own host, it does not enter the lobby.

Real-money play of any title still requires a signed aggregator (decision 0003)
plus a per-title BR certificate registered in `GameRegistry`.
