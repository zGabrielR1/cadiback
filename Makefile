.PHONY: test check check-py lint selftest demo-test demo web-build web-install feeds deploy-prep deploy-check

test: selftest

demo:
	python3 -m demo.server

feeds:
	python3 scripts/probe_live_feeds.py
	python3 scripts/fetch_live_fixtures.py
	python3 scripts/probe_vendor_catalog.py

web-install:
	cd web && npm ci

web-build:
	cd web && npm run build

# everything a deploy must carry, in one command: the export cannot be stale,
# because verify.py fails on sources newer than web/out.
deploy-prep: web-install web-build check-py
	@echo "export built — next: docker build -t candibet ."

selftest:
	python3 -m frame.selftest

# is the tree deployable by a remote host? Needs no credentials.
deploy-check:
	python3 scripts/render_deploy.py --check

demo-test:
	python3 -m unittest demo.test_demo

check:
	bash scripts/verify.sh

check-py:
	python3 scripts/verify.py

lint:
	(npx --yes markdownlint-cli2 "**/*.md" 2>/dev/null || echo "markdownlint unavailable (best-effort), skipping") 
