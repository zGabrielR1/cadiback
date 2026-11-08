# 0105 — Isolate malformed recent-game cache data

Date: 2026-10-28

## Selection and evidence

Compared further casino feed recovery (other polls also have silent catches), cache isolation, and completing restricted release gates. Selected the cache because a local fixture directly reproduced readRecent throwing TypeError: Cannot convert object to primitive value. The raw JSON entry used ts:{valueOf:null,toString:null}; Number(entry.ts) threw outside the storage/JSON catches. This contradicted the module's best-effort read contract. Cached IDs/provider/title/category also reached string operations or React children without type checks. HTTP and visual gates still depend on execution capabilities unavailable in prior runs; other feed changes are not part of this objective.

## Contract

- Accept only nonblank string recent IDs; preserve their exact values.
- Snapshot rendering requires nonblank string ID/title, optional string metadata and numeric/string RTP. A malformed or mismatched snapshot becomes null while its valid outer recent ID/order remains available for the live catalog. Missing optional metadata is not invented.
- Convert only primitive number/string timestamps. Nonfinite/malformed time becomes zero, preserving the existing unknown-time convention without object coercion.
- Invalid rememberGame input does not write or replace existing stored bytes. Valid snapshots still retain only the existing KEEP fields. No new storage format, migration or compatibility path.
- Preserve existing deduplication, date ordering, 30-entry limit, clearing and quota fallback to ID-only rows. The existing decoder still handles its already-supported shapes.

This is cache/display integrity, not a general validator for live catalog data or launch URLs.

## Verification and skeptical review

Added seven independent cache tests: malformed timestamp ordering; invalid identities/mismatched snapshots; invalid labels/metadata; valid writes with exact labels/field trimming/limit/deduplication; invalid-write non-mutation; quota fallback/clear; and corrupt/denied/unavailable storage. Run them against original HEAD in an isolated temporary copy: four fail. With the patch all pass. No real browser storage is touched; tests use in-memory storage and restore globals.

All 272 historical probes/provider-demos.json snapshots pass remember/read memory-storage round trips. This checks current stored catalog shapes, not live provider availability. Every accepted row keeps valid labels and metadata without stringifying objects or trimming identities.

Final verification:58 JavaScript tests across12 files,73 existing static component renders, core50/50, fresh production export and structure verifier zero problems pass. Scoped diff check clean. Backend426 run:399 pass,27 errors, all sandbox HTTP-binding PermissionErrors. Logs:/tmp/operator-0105-{baseline,node,render,core,build,backend}.log.

No UI layout, API, ledger, storage schema, dependencies, harness change or deployment. No new browser attempt or live identity/payment mutations. Prior0102–0104 changes and unrelated edits remain intact. Release gates still require real HTTP execution and browser/viewport checks for0104; local cache tests do not satisfy them.
