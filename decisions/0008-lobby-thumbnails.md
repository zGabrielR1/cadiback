# 0008 — Lobby thumbnails: publisher artwork cached locally

Date: 2026-10-05. Status: decided (amends 0006 for hobby scope).

0006 forbade copying publisher artwork into the repo. For a 1:1 hobby
simulation, offline-capable loading needs local bytes, so we cache each
title's official cover thumbnail from the publisher's own site
(`scripts/fetch-covers.py`, stored as `cover` in `probes/provider-demos.json`,
files in `games/` + `web/public/games/`). Scope is limited to lobby
thumbnails; no game code, RNG, or launchable assets are rehosted, and
decision 0006's security and cert-gate reasoning is unchanged. Falls back
to generated SVG covers (`scripts/make-covers.py`) when a title has no
official image.
