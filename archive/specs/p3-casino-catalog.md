# Casino Catalog & Aggregation Schema

This document details the casino aggregator schema, title certification format, and launch protocol (`frame/verticals/casino/`).

## 1. Catalog JSON Schema

Each title in the platform catalog complies with the following structure:

```json
{
  "game_id": "string (unique identifier, e.g. 'pp:gates-of-olympus')",
  "provider": "string (provider slug, e.g. 'pragmatic_play')",
  "title": "string (display title)",
  "category": "string (Slots | Crash | Mesa | Ao vivo | Originais)",
  "demo_url": "string (https launch URL)",
  "host": "string (whitelisted launcher domain)",
  "rtp": "number | null (return to player percentage)",
  "launchable": "boolean (true if active for play)",
  "wallet_isolated": "boolean (true for publisher demo execution)",
  "embed": "boolean (true for iframe theater integration)"
}
```

## 2. Launch Seam & Security Gates

1. **Host Whitelist (`DEMO_HOSTS`)**:
   - `demogamesfree.pragmaticplay.net`
   - `demogamesfree-asia.pragmaticplay.net`
   - `static-live.hacksawgaming.com`
   - `asccw.playngonetwork.com`
   - `games.evolution.com`
   - `demo.spribe.io`
   - `m.pgsoft-games.com`
   - `static.pgsoft-games.com`
2. **Protocol Enforcement**:
   - Only `https://` schemes are admitted into the lobby.
3. **Player Session Continuity**:
   - Player identity and wallet balances remain preserved across game switches via the top-level app store.
