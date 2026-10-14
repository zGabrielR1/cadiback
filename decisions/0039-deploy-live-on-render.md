# 0039 — the deploy is live on Render: two failures that said nothing

**Date:** 2026-10-14
**Status:** accepted — `https://cadiback.onrender.com` is up and serving.

Decision 0038 made the deploy independent of the build machine. It did not
make it work: every deploy since the service was created had failed, and
neither the API, nor the deploy object, nor the service object said why. Two
separate faults, both invisible from the outside.

## The service was never using our Dockerfile

Render's `POST /services` creates a **Python** service by default. It reads
`requirements.txt`, ignores the `Dockerfile` sitting in the repository
root entirely, and fails in seconds:

```
Using Python version 3.14.8 (default)
Using Poetry version 2.1.3 (default)
Running build command 'pip install -r requirements.txt'...
ERROR: Could not open requirements file: [Errno 2] No such file or directory
```

The service object *claimed* `"runtime": "docker"`, `"env": "docker"`,
`"envSpecificDetails": {"dockerfilePath": "./Dockerfile"}`. All three fields
looked right and the build ignored all three. `runtime` is the field the API
echoes back; **`env` is the field it switches on**, and the two Dockerfile
paths have to sit beside it. `configure()` now sends `env`, `dockerContext`
and `dockerfilePath` together with `runtime`.

This is why "check the dashboard" was never going to be the answer: the
dashboard would have shown the same four Python-buildpack lines.

## The image died at the last step

With the builder switched, the build ran properly and produced the whole
storefront in-image — then failed on line 54:

```
#23 [stage-1 7/7] RUN useradd --create-home --shell /bin/false operator && …
#23 useradd: group operator exists - if you want to add this user to that
    group, use -g.
#23 ERROR: … exit code: 9
```

`python:3.14-slim` is Debian trixie, and Debian ships an **`operator` group**
(systemd's, GID 37). `useradd operator` without `-g` tries to create a group
of that name, fails, and exits 9. On Windows this line cannot fail, which is
why no amount of local verification caught it.

`groupadd -f operator` first (idempotent: succeeds with a warning if the
group is already there), then `useradd -g operator` to use it. The same fix
is what makes the image survive the next base-image bump.

## A `build_failed` is a status, not a reason

`GET /services/{id}/deploys/{deployId}` answers `build_failed` and stops
there. There is no `/logs` under a service, and no `/builds`. The output is
in one place only:

```
GET /logs?ownerId=<tea-…>&startTime=<deploy.createdAt>&endTime=…
       &direction=forward&resource=<srv-…>
```

`ownerId` is required, `resource` is required, and the query-parameter names
are `startTime` / `endTime` / `resource` — not the `resourceId[]`,
`resourceType` or `serviceId` variants, each of which is rejected with
`invalid path`. The stream carries the build output verbatim, ANSI escapes
included.

`render_deploy.py` now reads it and prints the lines that matter on a
failure, so a deploy reports its own cause instead of pointing at a browser
this machine does not have.

## Credentials and repository

The key was already on this machine, in the repository root as `.env.render`
(a single bare line, gitignored) — a location the driver did not know about,
so every earlier run had to be driven by hand. It reads that file now, and it
takes **the repository from the git remote** rather than a second hand-kept
copy: a deploy can no longer disagree with where the code actually lives.

## Verified live

| Check | Result |
| --- | --- |
| `/api/health` | 200, `status: ok`, books balance |
| `/api/catalog` | 10 in-house + **182** publisher rows |
| `/` | 200, the storefront, `_next` assets resolve |
| `/g/pp:gates-of-olympus/` | 200, 95 874 b, live publisher through the proxy |
| `/g/hs:chaos-crew/` | 200, 40 240 b |
| `/g/pgo:book-of-dead/` | 200, launcher |
| `/api/health` proxy counters | `upstream: 3, failures: 0, bytes: 136720` |

The service is named **`cadiback`** and answers at
**`https://cadiback.onrender.com`** — the account already held a service by
the repository's name, and creating a second one beside it would have left
two services, one of them broken. `find_service()` matches on the repository
before the name for exactly that reason.

Free plan, `numInstances: 1`: no disk, so the ledger resets when the instance
is recycled, and a cold start takes ~30s. Both are in `render.yaml`.
