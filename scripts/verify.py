"""Portable superset of scripts/verify.sh (for hosts without bash).
Same exit contract: 0 = OK, 1 = FAILED. Adds the demo/, web/ (export
existence, asset references, freshness, markers) and full-tree checks.
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
fail = []

required = ["AGENTS.md", "ARCHITECTURE.md", "PROGRESS.md", "CURRENTTASK",
            "README.md", "Makefile", "docs/gap-assessment.md"]
required += [os.path.join(p, n) for p, n in [
    ("frame/core", "money.py"), ("frame/core", "ids.py"), ("frame/core", "ledger.py"),
    ("frame/core", "devig.py"), ("frame/wallet", "books.py"),
    ("frame/validation", "gates.py"), ("frame/compliance", "sigap.py"),
    ("frame/models", "registry.py"),
    ("frame/verticals/sports", "contract.py"), ("frame/verticals/sports", "stub.py"),
    ("frame/verticals/sports", "pricing.py"),     ("frame/verticals/sports", "espn_engine.py"), ("frame/verticals/sports", "superbet_engine.py"),
    ("frame/verticals/casino", "stub.py"), ("frame/ops", "scheduler.py"),
    ("frame/ops", "notifier.py"), ("frame/ops", "health.py"),
    ("demo", "server.py"), ("demo", "slot.py"), ("demo", "payments.py"),
    ("demo", "risk.py"), ("demo", "sports_data.py"),    ("demo", "vendor.py"),
    ("demo", "odds_engine.py"),
    ("demo", "auth.py"),
    ("demo", "game_proxy.py"),
    ("demo", "index.html"), ("frame", "selftest.py"),
    ("frame/tests", "test_frame.py"), ("demo", "test_demo.py"),
    ("scripts", "probe_live_feeds.py"), ("scripts", "fetch_live_fixtures.py"),
    ("scripts", "render_deploy.py"),
    ("web/app", "page.jsx"), ("web/app", "layout.jsx"),
    ("web/app", "globals.css"),    ("web/lib", "api.js"),
    ("web/app", "error.jsx"),
    ("web/app", "components/CasinoHome.jsx"),
    ("web/app", "components/SportsHome.jsx"),
    ("web/app", "components/AdminPanel.jsx"),
    ("web", "next.config.js"),
    ("web", "package.json"),
]]
for path in required:
    if not os.path.isfile(path):
        fail.append(f"missing {path}")

py_sources = []
for base, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in {"node_modules", "__pycache__",
                                             ".next", "out", ".git"}]
    py_sources += [os.path.join(base, f) for f in files if f.endswith(".py")]
for src in py_sources:
    # compile in memory: writing .pyc beside every source dirtied the tree
    # on every verification run
    try:
        with open(src, "r", encoding="utf-8") as handle:
            compile(handle.read(), src, "exec")
    except (SyntaxError, ValueError) as exc:
        fail.append(f"py_compile failed: {src}: {exc}")

# web: the served storefront must exist, reference assets that exist, and be
# built from the current sources (a stale export serves yesterday's site)
export_index = os.path.join("web", "out", "index.html")
if not os.path.isfile(export_index):
    fail.append("missing web/out/index.html (build: cd web && npm run build)")
else:
    with open(export_index, "r", encoding="utf-8", errors="replace") as handle:
        export_html = handle.read()
    export_refs = set(re.findall(r'(?:src|href)="(/_next/[^"]+)"', export_html))
    for ref in sorted(export_refs):
        asset = os.path.join("web", "out", *ref.strip("/").split("/"))
        if not os.path.isfile(asset):
            fail.append(f"export references a missing asset: {ref}")
    built_at = os.path.getmtime(export_index)
    web_sources = ["web/next.config.js", "web/package.json"]
    for web_base in ("web/app", "web/lib", "web/public"):
        for web_dir, _web_dirs, web_files in os.walk(web_base):
            web_sources += [os.path.join(web_dir, f) for f in web_files]
    stale = [p for p in web_sources
             if os.path.isfile(p) and os.path.getmtime(p) > built_at + 1.0]
    for path in sorted(stale):
        fail.append(f"stale export: {path} newer than web/out/index.html "
                    "(rebuild: cd web && npm run build)")

link_re = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
broken = []
for base, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in {"node_modules", "__pycache__",
                                             ".next", "out", ".git"}]
    for name in files:
        if not name.endswith(".md"):
            continue
        doc = os.path.join(base, name)
        with open(doc, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        for link in link_re.findall(text):
            if link.startswith(("http", "mailto:", "#")):
                continue
            target = link.split("#")[0]
            if not target:
                continue
            # resolve against the document's own directory, not the repo root
            resolved = os.path.normpath(
                os.path.join(base, target.replace("/", os.sep)))
            if not os.path.exists(resolved):
                broken.append(f"{doc}: {link}")
fail += broken

markers = []
# every shipping module, not just frame/: demo/ and scripts/ ship too
for base, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in {"node_modules", "__pycache__",
                                             ".next", "out", ".git"}]
    for name in files:
        if not name.endswith(".py") or name.startswith("test_"):
            continue
        path = os.path.abspath(os.path.join(base, name))
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            body = handle.read()
        if path == os.path.abspath(__file__):
            continue
        if re.search(r"TODO|FIXME|XXX|HACK", body):
            markers.append(path)
# web sources follow the same "finish the code, do not annotate it" rule
for base, dirs, files in os.walk("web"):
    dirs[:] = [d for d in dirs if d not in {"node_modules", ".next", "out"}]
    for name in files:
        if not name.endswith((".js", ".jsx", ".css")):
            continue
        doc = os.path.join(base, name)
        with open(doc, "r", encoding="utf-8", errors="replace") as handle:
            if re.search(r"TODO|FIXME|XXX|HACK", handle.read()):
                markers.append(doc)
fail += [f"fragment markers in {p}" for p in markers]

print(f"verify: {len(required)} files, {len(py_sources)} py sources, "
      f"{len(fail)} problems")
for problem in fail:
    print("FAIL:", problem)
print("check: OK" if not fail else "check: FAILED")
sys.exit(1 if fail else 0)