"""Create (or find) the Render service and deploy it, without a browser.

The Render dashboard is the usual way in, but it is also three manual steps
and a browser session. This does the same work over the public REST API:

    # credentials, either in the environment...
    export RENDER_API_KEY=rnd_...          # dashboard > Account > API Keys
    export RENDER_REPO=https://github.com/<you>/<repo>
    # ...or in two files next to your home (never in the repository):
    #   ~/.render_api_key   one line, the key
    #   ~/.render_repo      one line, the repository URL
    python scripts/render_deploy.py

The repo must exist and contain this tree (public, or connected to the same
account). `render.yaml` is the contract; this script sends the same settings
explicitly so it also works where a Blueprint is not picked up.

Three modes:

    python scripts/render_deploy.py --check     # is the tree deployable?
    python scripts/render_deploy.py --url-only  # where is it, if it exists?
    python scripts/render_deploy.py             # create/update, deploy, watch

`--check` needs nothing but the tree, so it can be run before any credential
exists — and it is the reason the deploy does not depend on the machine that
built it: the Dockerfile builds `web/out` itself, so no artifact has to be
committed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.render.com/v1"

# The service contract, mirroring render.yaml. Kept in one place so the
# script and the Blueprint cannot drift apart silently.
SERVICE = {
    "name": "candibet",
    "type": "web_service",
    "runtime": "docker",
    "plan": "free",
    "dockerfilePath": "./Dockerfile",
    "branch": "main",
    "healthCheckPath": "/api/health",
    # Render routes to 0.0.0.0:$PORT. Without HOST the server binds 127.0.0.1
    # and the deploy answers "connection refused" forever.
    "envVars": [
        {"key": "HOST", "value": "0.0.0.0"},
        {"key": "OPERATOR_DATA_DIR", "value": "/data"},
    ],
}

# Files the image must be able to build and run without anything else.
REQUIRED = ["Dockerfile", ".dockerignore", "render.yaml",
            "web/package.json", "web/package-lock.json", "web/next.config.js",
            "web/app/page.jsx", "frame/__init__.py", "demo/server.py",
            "probes/provider-demos.json"]

# Paths the image needs and the build context must therefore NOT exclude: the
# Dockerfile's first stage builds the storefront from these.
MUST_REACH_IMAGE = ["web/app", "web/lib", "web/public",
                    "web/package.json", "web/package-lock.json",
                    "web/next.config.js", "frame", "demo", "probes"]


def _patterns(name: str) -> list[str]:
    path = os.path.join(ROOT, name)
    if not os.path.isfile(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.rstrip("/"))
    return out


def _tracked(path: str) -> list[str]:
    """Files git is tracking under `path` (empty if there is no repo/git)."""
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        return []
    try:
        result = subprocess.run(["git", "-C", ROOT, "ls-files", "--", path],
                                capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def check_tree() -> int:
    """Report whether this tree can be built by a remote host."""
    problems: list[str] = []
    for path in REQUIRED:
        if not os.path.isfile(os.path.join(ROOT, path)):
            problems.append(f"missing {path}")

    ignored = set(_patterns(".dockerignore")) | set(_patterns(".gitignore"))
    for path in MUST_REACH_IMAGE:
        if any(path == pat or path.startswith(pat + "/") for pat in ignored):
            problems.append(f"{path} is ignored: the image builds the storefront "
                            "from source and cannot without it")

    dockerfile = ""
    if os.path.isfile(os.path.join(ROOT, "Dockerfile")):
        dockerfile = open(os.path.join(ROOT, "Dockerfile"),
                          encoding="utf-8").read()
        if "COPY --from=storefront" not in dockerfile:
            problems.append("Dockerfile does not copy the storefront from a "
                            "build stage: the export would have to be committed, "
                            "and the deploy would depend on the build machine")

    committed = _tracked("web/out")
    if committed:
        problems.append(f"{len(committed)} file(s) of web/out are committed: a "
                        "build artifact in the repository goes stale silently")
    elif os.path.isdir(os.path.join(ROOT, "web/out")):
        print("note: web/out exists locally and is ignored — the image builds "
              "its own copy, so this one cannot reach it")

    print(f"render preflight: {len(REQUIRED)} files checked, "
          f"{len(problems)} problem(s)")
    for problem in problems:
        print("FAIL:", problem)
    print("check: OK" if not problems else "check: FAILED")
    return 1 if problems else 0


# Where the credentials come from when they are not in the environment. A
# deploy key is a credential, and handing it over through a file keeps it out
# of a chat transcript and out of the repository. `setx` is deliberately not
# offered: a child process inherits its parent's environment, not the
# registry, so a variable set there never reaches this script.
KEY_FILE = os.path.join(os.path.expanduser("~"), ".render_api_key")
REPO_FILE = os.path.join(os.path.expanduser("~"), ".render_repo")


def _first_line(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip().splitlines()[0].strip()


def read_key() -> str:
    """The Render API key: environment first, then `~/.render_api_key`."""
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if key:
        return key
    return _first_line(KEY_FILE) if os.path.isfile(KEY_FILE) else ""


def read_repo() -> str:
    """The repository Render builds from: environment, or `~/.render_repo`."""
    repo = os.environ.get("RENDER_REPO", "").strip()
    if repo:
        return repo
    return _first_line(REPO_FILE) if os.path.isfile(REPO_FILE) else ""


class RenderError(RuntimeError):
    """Render said no, or could not be reached. Always reported, never raised
    as a traceback: a wrong key is an operator mistake, not a crash."""


def _call(path: str, key: str, payload: dict | None = None,
          method: str = "GET") -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        hint = ""
        if exc.code in (401, 403):
            hint = (" — the key is wrong, expired, or cannot see this account; "
                    "check dashboard > Account > API Keys")
        raise RenderError(f"{exc.code} {exc.reason}{hint}\n  {detail}") from exc
    except urllib.error.URLError as exc:
        raise RenderError(f"cannot reach {API}: {exc.reason}") from exc
    except ValueError as exc:
        raise RenderError(f"unreadable answer from {path}: {exc}") from exc


def find_service(key: str) -> dict | None:
    """The service we already own, if it exists."""
    cursor = None
    while True:
        path = "/services?limit=100" + (f"&cursor={cursor}" if cursor else "")
        page = _call(path, key)
        for service in page:
            if service.get("name") == SERVICE["name"]:
                return service
        cursor = page[-1].get("cursor") if page else None
        if not cursor:
            return None


def create_service(key: str, repo: str) -> dict:
    body = dict(SERVICE, repo=repo)
    body["envVars"] = [{"key": item["key"], "value": item["value"]}
                       for item in SERVICE["envVars"]]
    try:
        return _call("/services", key, body, "POST")
    except RenderError as exc:
        raise RenderError(
            f"{exc}\n  Most common cause: the repository must be public, or "
            "connected to this account, and `main` must exist in it.") from exc


def deploy(service_id: str, key: str) -> str:
    """Kick a deploy and watch it to a terminal state."""
    trigger = _call(f"/services/{service_id}/deploys", key,
                    {"clearCache": "do_not_clear"}, "POST")
    deploy_id = trigger.get("id", "")
    print(f"deploy {deploy_id}: building…")
    seen = ""
    for _ in range(180):           # ~30 min at 10s
        time.sleep(10)
        status = _call(f"/services/{service_id}/deploys/{deploy_id}", key)
        state = f"{status.get('status')} {(status.get('commit') or {}).get('shortHash', '')}"
        if state != seen:
            print(" ", state)
            seen = state
        if status.get("status") in ("live", "build_failed", "update_failed",
                                    "canceled", "pre_deploy_in_progress"):
            return status["status"]
    return "timeout"


def run(key: str, repo: str, force: bool) -> int:
    """Find or create the service, deploy it, watch it go live."""
    existing = find_service(key)
    if existing and not force:
        url = existing.get("serviceDetails", {}).get("url")
        print(f"service candibet already exists: {url or '(no url yet)'}")
        print("re-run with --yes to deploy the current commit")
        return 0
    if check_tree():
        print("refusing to deploy a tree that fails preflight")
        return 1
    service = existing or create_service(key, repo)
    service_id = service["id"]
    print(f"service: {service.get('name')} [{service_id}]")
    print(f"url:     {service.get('serviceDetails', {}).get('url')}")
    outcome = deploy(service_id, key)
    print("deploy:", outcome)
    if outcome != "live":
        print("not live — read the build log in the dashboard, or "
              f"{API}/services/{service_id}/deploys")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="only verify the tree is deployable")
    parser.add_argument("--repo", default=read_repo(),
                        help="https://github.com/<you>/<repo>")
    parser.add_argument("--yes", action="store_true",
                        help="deploy even if the service already exists")
    parser.add_argument("--url-only", action="store_true",
                        help="print the existing service's URL and exit")
    args = parser.parse_args()

    if args.check:
        return check_tree()
    try:
        key = read_key()
        if not key:
            print(f"no Render API key: set RENDER_API_KEY, or put one line in "
                  f"{KEY_FILE}")
            return 2
        if args.url_only:
            existing = find_service(key)
            url = (existing or {}).get("serviceDetails", {}).get("url")
            print(url or "no candibet service on this account yet")
            return 0 if existing else 1
        if not args.repo:
            print(f"need the repository: set RENDER_REPO, or put one line in "
                  f"{REPO_FILE}")
            return 2
        return run(key, args.repo, args.yes)
    except RenderError as exc:
        print(f"render: {exc}")
        return 3
    except KeyboardInterrupt:
        print("interrupted; the deploy may still be running on Render")
        return 130


if __name__ == "__main__":
    sys.exit(main())