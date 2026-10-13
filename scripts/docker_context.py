"""Reproduce what Docker would see, from the tree Render will clone.

Render's build log lives only in its dashboard, so a failed build is read by
reproducing the context locally: apply the `.dockerignore` rules to the
committed file list, then check that every `COPY` source in the Dockerfile
survives. A `COPY` whose source was excluded fails the build in seconds —
which is what a build that dies before any compilation looks like.

    python scripts/docker_context.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Sources the Dockerfile copies, and the stage they are copied in.
COPY_STAGE = {
    "frame": "runtime", "demo": "runtime", "probes": "runtime",
    "web/package.json": "storefront", "web/package-lock.json": "storefront",
    "web/next.config.js": "storefront", "web/app": "storefront",
    "web/lib": "storefront", "web/public": "storefront",
}

# Copied fine, emptied silently: the build succeeds and the site ships broken.
REQUIRED_CONTENT = {
    "web/public/games": "every cover the lobby cards load",
    "demo": "the server itself",
    "frame": "the wallet core",
    "probes": "the provider catalogue the lobby reads at startup",
}


def dockerignore_patterns() -> list[str]:
    path = os.path.join(ROOT, ".dockerignore")
    if not os.path.isfile(path):
        return []
    return [line.strip().rstrip("/") for line in open(path, encoding="utf-8")
            if line.strip() and not line.strip().startswith("#")]


def excluded(path: str, patterns: list[str]) -> bool:
    """Whether `.dockerignore` keeps this path out of the build context.

    Modelled on Docker's own rule, not git's: a pattern **without a slash
    matches at any depth**, so a top-level `games` line also removes
    `web/public/games` — which is every cover the storefront loads. That is
    not a subtlety to guess at, it is why this matcher exists: the image
    builds without a cover and nothing says so.
    """
    segments = path.split("/")
    for pattern in patterns:
        if pattern in ("*", "**"):
            return True
        if "/" not in pattern and pattern not in ("**",):
            # any single path segment equal to this, at any depth
            if pattern in segments or \
                    (pattern.startswith("*") and pattern.endswith("*")
                     and any(segment.startswith(pattern[1:-1])
                             for segment in segments)):
                return True
            continue
        if path == pattern or path.startswith(pattern.rstrip("/") + "/"):
            return True
        if "**" in pattern:
            head = pattern.split("**", 1)[0].rstrip("/")
            tail = pattern.split("**", 1)[1].lstrip("/")
            if head and not path.startswith(head + "/"):
                continue
            rest = path[len(head) + 1:] if head else path
            if not tail:
                return True
            if re.fullmatch(tail.replace("*", "[^/]*"), rest):
                return True
    return False


def committed_files(ref: str = "HEAD") -> list[str]:
    """What Render clones: the committed tree, not the working copy.

    The working copy carries what the deploy must NOT see (node_modules, the
    local ledger, a stale web/out), so checking it would answer a different
    question — and would hide exactly the bug this is here to find.
    """
    result = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only",
                             ref], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise SystemExit(f"git ls-tree failed: {result.stderr.strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    patterns = dockerignore_patterns()
    files = committed_files()
    kept = [f for f in files if not excluded(f, patterns)]
    dropped = len(files) - len(kept)

    print(f"docker context: {len(files)} committed files, "
          f"{len(patterns)} ignore rules -> {len(kept)} in, {dropped} out")

    problems: list[str] = []
    for source, stage in COPY_STAGE.items():
        present = [f for f in kept if f == source or f.startswith(source + "/")]
        if not present:
            problems.append(f"Dockerfile stage '{stage}' copies {source}/ but "
                            f".dockerignore leaves nothing of it in the context")
    # A directory that survived the COPY but lost its contents is the quiet
    # failure: the build succeeds and the site ships without its assets.
    for required, why in REQUIRED_CONTENT.items():
        kept_here = [f for f in kept if f.startswith(required)]
        if not kept_here:
            problems.append(f"{required} is empty in the build context: {why}")
    # A file that must be in the context for the *build* to work.
    for needed in ("Dockerfile", ".dockerignore"):
        if excluded(needed, patterns):
            problems.append(f"{needed} is excluded from its own build context")

    # The one file the runtime stage cannot do without: it copies from the
    # previous stage, so check the storefront build produced it by name.
    dockerfile = open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8").read()
    stage_copy = re.search(r"COPY --from=(\S+)\s+(\S+)\s+(\S+)", dockerfile)
    if not stage_copy:
        problems.append("Dockerfile does not copy web/out from a build stage: "
                        "the runtime image would ship no storefront")
    elif stage_copy.group(1) not in dockerfile.split("FROM ")[0] + dockerfile:
        problems.append(f"stage '{stage_copy.group(1)}' is never declared")

    total = sum(os.path.getsize(os.path.join(ROOT, f))
                for f in kept if os.path.isfile(os.path.join(ROOT, f)))
    print(f"context size: {total / (1024 * 1024):.1f} MB "
          f"(excluded from the context but tracked in git: "
          f"{', '.join(sorted({f.split('/')[0] for f in files if excluded(f, patterns)})) or 'none'})")
    for problem in problems:
        print("FAIL:", problem)
    print("check: OK" if not problems else "check: FAILED")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())