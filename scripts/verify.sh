#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fail=0
say() { printf '%s\n' "$*"; }
err() { printf 'FAIL: %s\n' "$*"; fail=1; }

cd "$ROOT"

for f in AGENTS.md ARCHITECTURE.md PROGRESS.md CURRENTTASK README.md Makefile; do
  [ -f "$f" ] || err "missing $f"
done

# web storefront: required sources + the export demo/server.py actually serves
# (verify.py is the superset — asset references, freshness, markers)
for f in web/app/page.jsx web/app/layout.jsx web/app/error.jsx \
         web/app/globals.css web/app/components/CasinoHome.jsx \
         web/app/components/SportsHome.jsx web/app/components/AdminPanel.jsx \
         web/lib/api.js web/next.config.js web/package.json \
         web/out/index.html; do
  [ -f "$f" ] || err "missing $f"
done

for f in frame/core/money.py frame/core/ids.py frame/core/ledger.py frame/core/devig.py \
         frame/wallet/books.py frame/validation/gates.py frame/compliance/sigap.py \
         frame/models/registry.py frame/verticals/sports/contract.py frame/verticals/sports/stub.py \
         frame/verticals/casino/stub.py frame/ops/scheduler.py frame/ops/notifier.py \
         frame/ops/health.py frame/selftest.py frame/tests/test_frame.py; do
  [ -f "$f" ] || err "missing $f"
done

python3 -m py_compile $(find frame -name '*.py') || err "py_compile failed"

grep -rEo '\[[^]]+\]\(([^)]+)\)' --include='*.md' . | sed -E 's/.*\(([^)]+)\)/\1/' | sort -u | while read -r link; do
  case "$link" in
    http*|mailto:*|"#") continue ;;
    */) [ -d "${link%/}" ] || { printf 'FAIL: dir link %s\n' "$link"; } ;;
    *\#*) target="${link%%\#*}"; [ -f "$target" ] || printf 'FAIL: file link %s\n' "$link" ;;
    *) [ -f "$link" ] || [ -d "$link" ] || printf 'FAIL: link %s\n' "$link" ;;
  esac
done | grep -q FAIL && fail=1 || true

if grep -rn "TODO\|FIXME\|XXX\|HACK" --include='*.py' frame/ | grep -v tests/ ; then
  err "fragment markers in frame/ (finish the code, do not annotate it)"
fi

if [ "$fail" -eq 0 ]; then say "check: OK"; else say "check: FAILED"; fi
exit "$fail"
