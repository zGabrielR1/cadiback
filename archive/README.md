# archive — retired paths, kept as code

Nothing in here is deployed. The live platform is the repository root:
`frame/`, `demo/`, `probes/`, `web/`, `Dockerfile`, `render.yaml`.

Everything here was working at some point and is kept because re-deriving it
is cheaper than remembering it. It is **code and small documents only** — the
heavy one-way captures (the superbet HTML mirror with its assets and
screenshots, the game-recon network logs, the duplicated cover set) were
discarded rather than carried; they were evidence for a decision already
written down in `decisions/`.

| Here | What it was | Why it stopped |
| --- | --- | --- |
| `deploy-worker/` | Cloudflare Worker fronting a Python backend behind a `cloudflared` quick tunnel (decision 0023) | two things expire: the tunnel hostname changes on every restart, and a `--temporary` account is reaped in about an hour. The last deploy, `candibet.road-hydrant.workers.dev`, no longer resolves |
| `deploy-fly.toml` | the Fly.io variant of the container route | Render is the host in use; the file is 25 lines and works if `fly` is ever wanted |
| `container/` | `Containerfile` + `frame.service` for a Cloudflare Container | same platform as the archived Worker, same expiry problem |
| `captures/mirror_superbet.py` | the mirror tool whose input was `examples/superbet/` | that capture was discarded; the tool is kept with the inputs it lost |
| `research/` | the two written analyses (sports data/odds, vendor & game architecture) | superseded by `frame/` and `demo/`; the raw network logs they were written from are gone |
| `specs/` | two design specs written before the build (sportsbook engine, casino catalog schema) | the code they describe exists; they are history, not instruction |

## If you are reaching for something here

- **To deploy:** nothing in this folder. `Dockerfile` + `render.yaml`, and
  `docs/deploy-easy.md` for the procedure.
- **To read why a deploy path died:** `docs/deploy-easy.md`, and decision
  0038 (the image builds its own storefront) which is what ended the
  build-machine dependency.
- **To change the proxy or the wallet:** `demo/game_proxy.py`, `demo/server.py`,
  and the decisions that explain them (0022–0037).

Moving something back is a `git mv` and a link fix; the code was never
modified on the way in.