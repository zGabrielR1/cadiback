"""Ensure an isolated Postgres for the release gate, then print its URL.

One command replaces the manual OPERATOR_TEST_DATABASE_URL setup:

    python scripts/bootstrap_test_db.py            # start via podman/docker, print URL
    OPERATOR_TEST_DATABASE_URL=$(python scripts/bootstrap_test_db.py) python scripts/release_gate.py

- If OPERATOR_TEST_DATABASE_URL is already set, reuse it (verified to be a
  postgres/postgresql URL; printed unchanged).
- Else start a disposable local Postgres in a throwaway container named
  `operator-test-pg` (podman preferred, docker fallback) on 127.0.0.1:5432
  with operator_test/operator_test/operator_test (CI-equivalent credentials),
  wait for readiness, and print the postgresql+psycopg:// URL.
- If a container with that name already exists, reuse it (idempotent).
- Never touches production DATABASE_URL or any env file. Cleanup with:
  podman rm -f operator-test-pg   (or: docker rm -f operator-test-pg)
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import time
from urllib.parse import urlsplit

CONTAINER = "operator-test-pg"
URL = "postgresql+psycopg://operator_test:operator_test@127.0.0.1:5432/operator_test"


def detect_runtime():
    if shutil.which("podman"):
        return "podman"
    if shutil.which("docker"):
        return "docker"
    return None


def run(runtime, *args, check=True):
    return subprocess.run([runtime, *args], capture_output=True, text=True, check=check)


def ensure(runtime):
    all_names = run(runtime, "ps", "-a", "--format", "{{.Names}}", check=False).stdout.splitlines()
    if CONTAINER in all_names:
        running = run(runtime, "ps", "--format", "{{.Names}}", check=False).stdout.splitlines()
        if CONTAINER not in running:
            run(runtime, "start", CONTAINER)
        return
    run(runtime, "run", "-d", "--name", CONTAINER,
        "-e", "POSTGRES_USER=operator_test",
        "-e", "POSTGRES_PASSWORD=operator_test",
        "-e", "POSTGRES_DB=operator_test",
        "-p", "127.0.0.1:5432:5432",
        "docker.io/library/postgres:16-alpine" if runtime == "podman" else "postgres:16-alpine")


def wait_ready(runtime, timeout=45):
    for _ in range(timeout):
        ready = run(runtime, "exec", CONTAINER, "pg_isready",
                    "-U", "operator_test", "-d", "operator_test", check=False)
        if ready.returncode == 0:
            return True
        time.sleep(1)
    return False


def main():
    existing = os.environ.get("OPERATOR_TEST_DATABASE_URL", "").strip()
    if existing:
        if urlsplit(existing).scheme not in ("postgres", "postgresql", "postgresql+psycopg"):
            raise SystemExit("OPERATOR_TEST_DATABASE_URL must be a Postgres URL")
        print(existing)
        return 0
    runtime = detect_runtime()
    if not runtime:
        raise SystemExit("no podman or docker available; set OPERATOR_TEST_DATABASE_URL yourself")
    ensure(runtime)
    if not wait_ready(runtime):
        raise SystemExit(f"test Postgres container {CONTAINER} did not become ready")
    print(URL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
