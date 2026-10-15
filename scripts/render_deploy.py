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
import re
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

# The fields that actually decide WHICH builder runs. A service created in the
# dashboard arrives as Render's Python default — it reads `requirements.txt`,
# ignores the Dockerfile entirely, and every build dies in seconds with
# "Could not open requirements file". `runtime` alone does not switch it: the
# switch is `env`, and the two Dockerfile paths sit beside it.
DOCKER_BUILD = {"env": "docker", "dockerContext": ".", "dockerfilePath":
                SERVICE["dockerfilePath"]}

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
#
# `.env.render` in the repository root is read too, because that is where this
# machine already keeps it. It is a single line holding the raw key (no
# `KEY=` prefix), and `.gitignore` excludes it; a `KEY=value` pair is accepted
# as well so the same file works either way.
KEY_FILE = os.path.join(os.path.expanduser("~"), ".render_api_key")
REPO_FILE = os.path.join(os.path.expanduser("~"), ".render_repo")
ENV_FILE = os.path.join(ROOT, ".env.render")

# The Asaas Pix rail (decision 0045, docs/asaas.md). These are secrets, so the
# repository only ever holds `sync: false` placeholders in `render.yaml`; the
# real values travel from here at deploy time.
ASAAS_ENV_FILE = os.path.join(ROOT, ".env.asaas")
ASAAS_KEYS = ("ASAAS_API_KEY", "ASAAS_CUSTOMER_ID", "ASAAS_WEBHOOK_SECRET",
              "ASAAS_BASE_URL")

# Resend email (decision 0047, docs/mail.md). Same shape: the repository holds
# `sync: false` placeholders, the real key travels from the local gitignored
# `.env.resend` at deploy time. MAIL_FROM is not secret but belongs with the
# key, so it is carried from the same file.
RESEND_ENV_FILE = os.path.join(ROOT, ".env.resend")
RESEND_KEYS = ("RESEND_API_KEY", "MAIL_FROM", "MAIL_FROM_NAME")

# Cloudflare Turnstile (decision 0048, docs/turnstile.md). The secret is the
# only sensitive value; the site key is public and the hostnames are an
# allowlist. All three are carried from the local gitignored `.env.turnstile`.
# `TURNSTILE_DEV_HOSTNAMES` (loopback, for local work) is deliberately NOT in
# this list: a production allowlist must never contain localhost.
TURNSTILE_ENV_FILE = os.path.join(ROOT, ".env.turnstile")
TURNSTILE_KEYS = ("TURNSTILE_SECRET_KEY", "TURNSTILE_SITE_KEY",
                  "TURNSTILE_HOSTNAMES")

# Supabase Postgres (decision 0049, docs/supabase.md). Only DATABASE_URL is
# carried: the Python backend is the sole database client, so the anon and
# service-role keys stay on the laptop (migrations run from here, by hand).
SUPABASE_ENV_FILE = os.path.join(ROOT, ".env.supabase")
SUPABASE_KEYS = ("DATABASE_URL",)


def _first_line(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip().splitlines()[0].strip()


def _from_env_file(*, want_key: bool) -> str:
    """The key or the repo out of the repository's own `.env.render`.

    Holds either a bare line or a `NAME=value` pair; the last matching pair
    wins so the file can carry both credentials and neither can shadow the
    other by position.
    """
    if not os.path.isfile(ENV_FILE):
        return ""
    names = ("RENDER_API_KEY",) if want_key else ("RENDER_REPO",)
    found = ""
    for line in open(ENV_FILE, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        if name.strip() in names and value.strip():
            found = value.strip()
    if not found and want_key:
        # a bare line: the key on its own, which is how this file started
        line = _first_line(ENV_FILE)
        found = line if line.startswith("rnd_") else ""
    return found


def read_key() -> str:
    """The Render API key: environment, then `.env.render`, then the home file."""
    for value in (os.environ.get("RENDER_API_KEY", "").strip(),
                  _from_env_file(want_key=True),
                  _first_line(KEY_FILE) if os.path.isfile(KEY_FILE) else ""):
        if value:
            return value
    return ""


def read_repo() -> str:
    """The repository Render builds from.

    The git remote this tree already has is the answer far more often than a
    typed-in URL, so it is consulted before either credential store: a
    deployment should never disagree with where the code actually lives.
    """
    try:
        result = subprocess.run(["git", "-C", ROOT, "remote", "get-url", "origin"],
                                capture_output=True, text=True, timeout=20)
        remote = result.stdout.strip()
        if result.returncode == 0 and remote.startswith(("https://", "http://",
                                                        "git@")):
            return remote.removesuffix(".git").replace("git@github.com:",
                                                       "https://github.com/")
    except (OSError, subprocess.SubprocessError):
        pass
    for value in (os.environ.get("RENDER_REPO", "").strip(),
                  _from_env_file(want_key=False),
                  _first_line(REPO_FILE) if os.path.isfile(REPO_FILE) else ""):
        if value:
            return value
    return ""


def _env_pairs(path: str) -> dict[str, str]:
    """`KEY=value` lines out of a dotenv file; comments and blanks ignored.

    An inline ` # note` is dropped so a value may carry a trailing comment,
    the same shape `demo/asaas.py` reads.
    """
    values: dict[str, str] = {}
    if not os.path.isfile(path):
        return values
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip()
        if name.strip() and value:
            values[name.strip()] = value
    return values


def read_asaas_env() -> list[dict]:
    """The Asaas settings to carry to the host, secrets included.

    The environment wins over the gitignored `.env.asaas`. A setting that is
    absent everywhere is simply not sent, so a deploy without credentials
    keeps the instant demo credit instead of half-configuring the rail.
    """
    values = _env_pairs(ASAAS_ENV_FILE)
    for name in ASAAS_KEYS:
        if os.environ.get(name, "").strip():
            values[name] = os.environ[name].strip()
    return [{"key": name, "value": values[name]}
            for name in ASAAS_KEYS if values.get(name)]


def read_resend_env() -> list[dict]:
    """The Resend settings to carry to the host.

    Same rule as Asaas: the environment wins over the gitignored `.env.resend`,
    and a setting absent everywhere is simply not sent — so a deploy without
    email keeps the console mailer instead of half-configuring the rail.

    `.env.resend` is accepted either as `KEY=value` lines or as a bare single
    key, the shape `.env.render` already uses (`_from_env_file`), because a
    credential file tends to get written whichever way is quickest at the time.
    """
    values = _env_pairs(RESEND_ENV_FILE)
    if not values.get("RESEND_API_KEY") and os.path.isfile(RESEND_ENV_FILE):
        line = _first_line(RESEND_ENV_FILE)
        if line.startswith("re_"):
            values["RESEND_API_KEY"] = line
    for name in RESEND_KEYS:
        if os.environ.get(name, "").strip():
            values[name] = os.environ[name].strip()
    return [{"key": name, "value": values[name]}
            for name in RESEND_KEYS if values.get(name)]


def read_turnstile_env() -> list[dict]:
    """The Turnstile settings to carry to the host.

    Same rule as Asaas/Resend: the environment wins over the gitignored
    `.env.turnstile`, and a setting absent everywhere is simply not sent — so
    a deploy without credentials does not gate the surface instead of
    half-configuring it. `TURNSTILE_DEV_HOSTNAMES` is intentionally excluded:
    loopback belongs on a laptop, never in a production allowlist.
    """
    values = _env_pairs(TURNSTILE_ENV_FILE)
    for name in TURNSTILE_KEYS:
        if os.environ.get(name, "").strip():
            values[name] = os.environ[name].strip()
    return [{"key": name, "value": values[name]}
            for name in TURNSTILE_KEYS if values.get(name)]


def read_supabase_env() -> list[dict]:
    """The database URL to carry to the host.

    Same rule as the other rails: the environment wins over the gitignored
    `.env.supabase`, and an absent URL is simply not sent — so a deploy
    without it keeps files instead of half-configuring Postgres. Only
    `DATABASE_URL` travels: the backend never uses the anon/service keys
    (the storefront never talks to Supabase directly).
    """
    values = _env_pairs(SUPABASE_ENV_FILE)
    for name in SUPABASE_KEYS:
        if os.environ.get(name, "").strip():
            values[name] = os.environ[name].strip()
    return [{"key": name, "value": values[name]}
            for name in SUPABASE_KEYS if values.get(name)]


def runtime_env() -> list[dict]:
    """Every environment variable the service runs with, secrets included."""
    return (SERVICE["envVars"] + read_asaas_env() + read_resend_env()
            + read_turnstile_env() + read_supabase_env())


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


def entity(answer, *names: str) -> dict:
    """One object out of an answer, whatever envelope it arrived in.

    Render is not consistent here and the docs do not say which is which:
    `/services` and `/owners` answer `[{"cursor": …, "service": {…}}]`, a
    single-service GET answers the object bare. Every read therefore unwraps
    instead of indexing, and `entities()` below handles the page of them.
    """
    if isinstance(answer, list):
        for item in answer:
            found = entity(item, *names)
            if found:
                return found
        return {}
    if not isinstance(answer, dict):
        return {}
    for name in names:
        found = answer.get(name)
        if isinstance(found, dict) and found:
            return found
    return answer if ("id" in answer or "name" in answer) else {}


def entities(answer, *names: str) -> list[dict]:
    """Every object of a kind in an answer (a page of them, usually one)."""
    items = answer if isinstance(answer, list) else [answer]
    out: list[dict] = []
    for item in items:
        if isinstance(item, list):
            out.extend(entities(item, *names))
            continue
        found = entity(item, *names)
        if found:
            out.append(found)
    return out


def cursor_of(answer) -> str:
    """The next-page cursor, wherever the envelope kept it."""
    items = answer if isinstance(answer, list) else [answer]
    for item in items:
        if isinstance(item, dict) and item.get("cursor"):
            return item["cursor"]
    return ""


def find_service(key: str, repo: str = "") -> dict | None:
    """The service that builds our repository, whatever it is named.

    Matched on the repository first, not on the name: an account created in
    the dashboard carries the repo's own name, and creating a second service
    beside it would be the wrong move — two of them, one of them broken.
    """
    cursor = None
    named: dict | None = None
    while True:
        path = "/services?limit=100" + (f"&cursor={cursor}" if cursor else "")
        page = _call(path, key)
        for service in entities(page, "service"):
            if repo and (service.get("repo") or "").rstrip("/").lower() == \
                    repo.rstrip("/").lower():
                return service
            if service.get("name") == SERVICE["name"]:
                named = service
        cursor = cursor_of(page)
        if not cursor:
            break
    return named if not repo else None


def find_owner(key: str) -> dict:
    """The account the service will belong to.

    Render requires an explicit owner: a personal account (`usr-…`) or one of
    the workspaces (`tea-…`). A personal key sees exactly one personal owner;
    when only workspaces are visible, the first is named so the choice is
    visible rather than silent.
    """
    answer = _call("/owners", key)
    owners = entities(answer, "owner")
    if not owners:
        raise RenderError("this key cannot see any account")
    personal = [o for o in owners if o.get("type") == "user"]
    chosen = personal[0] if personal else owners[0]
    if not personal and len(owners) > 1:
        print(f"note: several accounts on this key; using "
              f"{chosen.get('name')} ({chosen.get('type')})")
    return chosen


def configure(service_id: str, key: str) -> dict:
    """Make an existing service what `SERVICE` says it should be.

    A service created in the dashboard arrives as Render's Python default
    (`pip install -r requirements.txt`, gunicorn, no health check) whatever
    the repository holds — which cannot build this project. The runtime and
    the routing details are editable; `Dockerfile` at the repo root is Render's
    own default, which is where ours is.

    Environment variables are deliberately NOT sent here: `PATCH /services/{id}`
    does not own them, and a set smuggled into this request silently corrupts
    the service's whole environment (observed: the set collapsed to one junk
    variable and the app came up unconfigured). They go through
    `set_env_vars()` instead.
    """
    body = {
        "serviceDetails": {
            **DOCKER_BUILD,
            "runtime": SERVICE["runtime"],
            "plan": SERVICE["plan"],
            "healthCheckPath": SERVICE["healthCheckPath"],
            "numInstances": 1,
        },
    }
    _call(f"/services/{service_id}", key, body, "PATCH")
    return _call(f"/services/{service_id}", key)


def set_env_vars(service_id: str, key: str, env_list: list[dict]) -> None:
    """Write the service's environment through the endpoint that owns it.

    `/services/{id}/env-vars` takes the array as the body and replaces the set.
    It is the only place env vars are written; see `configure()` for why.
    """
    _call(f"/services/{service_id}/env-vars", key, env_list, "PUT")


def create_service(key: str, repo: str, owner: dict) -> dict:
    body = {**SERVICE, **DOCKER_BUILD, "repo": repo, "ownerID": owner["id"]}
    body.pop("envVars", None)  # set separately, via set_env_vars()
    try:
        return _call("/services", key, body, "POST")
    except RenderError as exc:
        raise RenderError(
            f"{exc}\n  Most common cause: the repository must be public, or "
            "connected to this account, and `main` must exist in it.") from exc


ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def build_log(service_id: str, key: str, since: str,
              owner_id: str = "", limit: int = 400) -> list[str]:
    """The build output of one deploy, newest last, as printable lines.

    A failed build says nothing at all through the API's deploy object — the
    status is `build_failed` and that is all. The reason is only in the log
    stream, and reading it here is the difference between "check the
    dashboard" (needs a browser session) and a deploy report you can read
    where you are. Only the lines that matter are kept: BuildKit's per-layer
    churn buries the one line that explains the failure.
    """
    if not owner_id:
        owners = entities(_call("/owners", key), "owner")
        if not owners:
            return []
        owner_id = owners[0]["id"]
    path = (f"/logs?ownerId={owner_id}&startTime={since}"
            f"&endTime={_now()}&limit={limit}&direction=forward"
            f"&resource={service_id}")
    try:
        entries = _call(path, key).get("logs", [])
    except RenderError:
        return []
    lines = []
    for entry in entries:
        text = ANSI.sub("", entry.get("message", "")).strip()
        if text and ("ERROR" in text or text.startswith("#") or "error:" in text
                     or "==>" in text or "DONE" not in text):
            lines.append(text)
    return lines


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def deploy(service_id: str, key: str) -> str:
    """Kick a deploy and watch it to a terminal state."""
    try:
        _call(f"/services/{service_id}/deploys", key,
              {"clearCache": "do_not_clear"}, "POST")
    except RenderError:
        pass  # the deploy still started; the answer was just unreadable
    # The POST's body is not reliable (observed: empty), and the newest deploy
    # in the list is the one it started — so the id comes from there.
    page = _call(f"/services/{service_id}/deploys?limit=1", key)
    started = entities(page, "deploy")
    if not started:
        raise RenderError("Render accepted the deploy but reported none")
    trigger = started[0]
    deploy_id = trigger.get("id", "")
    print(f"deploy {deploy_id}: building…")
    seen = ""
    for _ in range(180):           # ~30 min at 10s
        time.sleep(10)
        status = entity(_call(f"/services/{service_id}/deploys/{deploy_id}", key),
                        "deploy")
        state = f"{status.get('status')} {(status.get('commit') or {}).get('shortHash', '')}"
        if state != seen:
            print(" ", state)
            seen = state
        if status.get("status") in ("live", "build_failed", "update_failed",
                                    "canceled", "pre_deploy_in_progress"):
            if status.get("status") != "live":
                print_build_failure(service_id, key, trigger.get("createdAt", ""))
            return status["status"]
    return "timeout"


def print_build_failure(service_id: str, key: str, since: str) -> None:
    """Say what the build actually said, not just that it failed."""
    lines = build_log(service_id, key, since)
    if not lines:
        print("build failed and Render returned no build log to explain it "
              "(read it in the dashboard)")
        return
    print("the build said:")
    for line in lines[-25:]:
        print("   ", line.encode("ascii", "replace").decode()[:200])


def run(key: str, repo: str, force: bool) -> int:
    """Find or create the service, make it ours, deploy it, watch it go live."""
    existing = find_service(key, repo)
    if existing and not force:
        url = existing.get("serviceDetails", {}).get("url")
        print(f"service {existing.get('name')} already exists: "
              f"{url or '(no url yet)'}")
        print("re-run with --yes to deploy the current commit")
        return 0
    if check_tree():
        print("refusing to deploy a tree that fails preflight")
        return 1
    if existing:
        service = configure(existing["id"], key)
        print(f"reconfigured {existing.get('name')} -> "
              f"{service.get('serviceDetails', {}).get('runtime')} runtime")
    else:
        owner = find_owner(key)
        print(f"owner:  {owner.get('name')} [{owner.get('id')}]")
        service = create_service(key, repo, owner)
    service_id = service["id"]
    env_list = runtime_env()
    set_env_vars(service_id, key, env_list)
    carried = read_asaas_env()
    if carried:
        print(f"carrying {len(carried)} Asaas setting(s) from "
              f"{os.path.basename(ASAAS_ENV_FILE)}/environment")
    else:
        print("no Asaas credentials found: the deploy uses the instant demo credit")
    carried_mail = read_resend_env()
    if carried_mail:
        print(f"carrying {len(carried_mail)} email setting(s) from "
              f"{os.path.basename(RESEND_ENV_FILE)}/environment")
    else:
        print("no email credentials found: the deploy logs mail instead of sending")
    carried_turnstile = read_turnstile_env()
    if carried_turnstile:
        print(f"carrying {len(carried_turnstile)} Turnstile setting(s) from "
              f"{os.path.basename(TURNSTILE_ENV_FILE)}/environment")
    else:
        print("no Turnstile credentials found: login/signup are not bot-gated")
    carried_db = read_supabase_env()
    if carried_db:
        print(f"carrying {len(carried_db)} database setting(s) from "
              f"{os.path.basename(SUPABASE_ENV_FILE)}/environment")
    else:
        print("no DATABASE_URL found: the deploy keeps files")
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
            existing = find_service(key, args.repo or read_repo())
            url = (existing or {}).get("serviceDetails", {}).get("url")
            print(url or "no service for this repository on this account yet")
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