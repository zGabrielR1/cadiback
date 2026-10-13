#!/usr/bin/env bash
# Start the Python operator backend and a public cloudflared tunnel to it,
# for the Cloudflare Worker in this folder to proxy.
#
#   ./backend.sh            # backend on :8765 + quick tunnel
#
# Prints the https://<name>.trycloudflare.com URL to pass as BACKEND_ORIGIN.
# Run from the operator root so `frame` and `demo` are importable.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
port="${PORT:-8765}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared not found on PATH. Install:" >&2
  echo "  curl -L -o /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" >&2
  echo "  chmod +x /usr/local/bin/cloudflared" >&2
  exit 1
fi

echo "== starting backend on :$port =="
( cd "$root" && python3 -m demo.server ) &
backend_pid=$!
trap 'kill "$backend_pid" 2>/dev/null || true' EXIT

# wait for the backend to answer before opening the tunnel
for _ in $(seq 1 20); do
  if curl -sSfo /dev/null "http://127.0.0.1:$port/api/health" 2>/dev/null; then break; fi
  sleep 0.5
done

echo "== opening quick tunnel =="
cloudflared tunnel --url "http://127.0.0.1:$port" --no-autoupdate
