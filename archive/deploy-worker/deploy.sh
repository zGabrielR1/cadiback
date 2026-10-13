#!/usr/bin/env bash
# Publish candibet to Cloudflare Workers.
#
#   BACKEND_ORIGIN=https://<backend-host> ./deploy.sh
#
# Builds the Next.js export and deploys the Worker that serves it and proxies
# the dynamic surface to BACKEND_ORIGIN. With no Cloudflare credentials it
# deploys to a temporary (claimable) account; set CLOUDFLARE_API_TOKEN to
# deploy to your own account.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"

: "${BACKEND_ORIGIN:?set BACKEND_ORIGIN to the public backend origin (e.g. a cloudflared tunnel URL)}"

echo "== building web/out =="
( cd "$root/web" && npm run build )

echo "== deploying candibet -> $BACKEND_ORIGIN =="
cd "$here"
if [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  npx --yes wrangler deploy --var BACKEND_ORIGIN:"$BACKEND_ORIGIN"
else
  echo "(no CLOUDFLARE_API_TOKEN: deploying to a temporary claimable account)"
  npx --yes wrangler deploy --temporary --var BACKEND_ORIGIN:"$BACKEND_ORIGIN"
fi
