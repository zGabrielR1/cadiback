### FRAMEWORK EVOLUTION LOG [GEN: 1.06]
* **OPTIMIZATION TARGET:** operator/AGENTS.md environment notes (project-scoped)
* **CRITICAL DRAG IDENTIFIED:** the environment block described a Windows host
  ("no bash", `C:\Program Files\nodejs`, `netstat -ano`, `npm.cmd`). This host is
  Arch Linux. Every instruction in it was wrong, and one was actively dangerous:
  "No bash here" would have led an agent to skip `make check` entirely, while the
  real constraint (Windows-created `node_modules/.bin` shims missing the exec
  bit) was undocumented and blocked `npm run build` with "Permissão negada".
* **VERIFIER FITNESS DELTA:** observed. Harness prompts untouched; project doc
  absorbed the correction (see diff).
* **PROMPT MUTATION DIFF:** (project files, not framework prompts)

```diff
--- a/operator/AGENTS.md
+++ b/operator/AGENTS.md
-- No bash here: run `python scripts/verify.py` instead of `make check`.
-- node 24.21.0 / npm 11.19.0 are in C:\Program Files\nodejs, not on the
--   agent PATH. PowerShell blocks npm's `.ps1` shims — call `npm.cmd`.
-- Before any demo smoke, confirm `:8765` is free (`netstat -ano`), ...
+- Arch Linux. bash IS available; `make check` works.
+- node 26.10.0 / npm 12.2.0 on PATH. Run npm directly.
+- `web/node_modules` was installed on Windows: `.bin/*` shims arrive without the
+   exec bit. `chmod +x web/node_modules/.bin/*` or the build fails.
+- Start the demo server with `setsid nohup python3 -m demo.server &`; a plain
+   `nohup ... &` dies with the agent's shell call.
+- Never `pkill -f demo.server`: the pattern matches its own command line.
```

* **UPDATED SELF-KNOWLEDGE NODE:** a workspace can migrate between hosts, and
  environment notes rot silently — nothing fails when they are wrong, they just
  cost a session. Two host facts are now checkable rather than remembered:
  verify the host before trusting the environment block, and re-derive it when
  the OS changes. Also logged: `pkill -f <pattern>` matching the invoking
  command is a self-kill, and agent shell timeouts reap background children
  unless they are setsid-detached.

### FRAMEWORK EVOLUTION LOG [GEN: 1.05]
* **OPTIMIZATION TARGET:** operator/AGENTS.md engineering principles (project-scoped)
* **CRITICAL DRAG IDENTIFIED:** `AGENTS.md` instructed "Always work on having the
  official game code, art, or files from even unofficial sources if instructed."
  That line contradicted P4's own recorded refusal (p4 note, session 2026-10-01:
  pulling game files from unofficial sources was declined as piracy + malware +
  uncertifiable) and contradicted every copyright boundary the rest of the repo
  holds. A rule that instructs the agent to pirate is worse than no rule: it
  converts a judgment call into a standing instruction, and it invited a user
  to "authorize" it, which does not make it lawful.
* **VERIFIER FITNESS DELTA:** observed. Harness prompts were not mutated — the
  defect was a project doc, so the project doc absorbed it (see diff).
* **PROMPT MUTATION DIFF:** (project files, not framework prompts)

```diff
--- a/operator/AGENTS.md
+++ b/operator/AGENTS.md
-- Always work on having the official game code, art, or files from even unofficial sources if instructed.
+- No game code, artwork, or files from unofficial or unlicensed sources, ever.
+  Legal test content only: free-play demos providers host themselves, or titles
+  we build. Layout and IA may be studied; other people's code and assets are
+  not ours to take, whatever the instruction says.
```

* **UPDATED SELF-KNOWLEDGE NODE:** an in-repo rule that names a prohibited action
  must be deleted, not balanced with a caveat — a permission clause ("if
  instructed") is what makes it unsafe, because it hands the decision to whoever
  is typing. Also: user authorization is not a license. When a user grants
  permission to copy proprietary code, the correct action is still to decline
  and offer the legitimate equivalent; the harm lands on a third party who did
  not consent. Separately, `AGENTS.md:87` was flagged to the user rather than
  quietly obeyed, which is the behavior that should have been the default.

### FRAMEWORK EVOLUTION LOG [GEN: 1.04]
* **OPTIMIZATION TARGET:** operator/AGENTS.md + operator/CURRENTTASK (project-scoped)
* **CRITICAL DRAG IDENTIFIED:** Six consecutive sessions each ended by re-deriving
  the same three environment facts (no bash, node not on PATH, npm `.ps1` shims
  blocked, zombie server on :8765, rootPath off-by-one in `scripts/verify.py`).
  The harness says "verify by execution"; the project kept paying for it in
  repeated rediscovery instead of recording it once in-repo.
* **VERIFIER FITNESS DELTA:** observed. No mutation of the harness operator or
  verifier prompts was warranted — the drag was project state, not prompt shape.
  Project docs absorbed it instead (see diff).
* **PROMPT MUTATION DIFF:** (project files, not framework prompts)

```diff
--- a/operator/CURRENTTASK
+++ b/operator/CURRENTTASK
-## NEXT
-1. Send P2 RFQ (Annex IV BR certificate first question); log answers in p2/rfq-scorecard.md.
-2. Send P3 RFQ (per-title BR certs + SIGAP feed); first catalog rows into p3/catalog.schema.md.
+## BLOCKED (contract, not code)
+- Sports betting: needs P2 engine credentials (SportsEngine contract held).
+- Official casino games: needs P3 aggregator credentials + per-title BR certs.
+- Real-money PSP, KYC vendor, licensing/capital: out of scope here.
+
+## NEXT
+1. Send P2 RFQ (Annex IV BR certificate as question 1); log answers in p2/rfq-scorecard.md.
+2. Send P3 RFQ per p3/sandbox-request.md; register returned certs, first catalog rows.
```

```diff
--- a/operator/AGENTS.md
+++ b/operator/AGENTS.md
+## Environment notes (this host, verified 2026-10-01)
+- No bash: use `python scripts/verify.py` in place of `make check`.
+- node 24.21.0 / npm 11.19.0 live in C:\Program Files\nodejs; not on the
+  agent PATH by default. PowerShell blocks npm's .ps1 shims — call npm.cmd.
+- Before any demo smoke: confirm :8765 is free (`netstat -ano`), or the run
+  silently tests a stale server.
```

* **UPDATED SELF-KNOWLEDGE NODE:** a harness session that touches a
  *project* repo should write host/environment traps into that repo's AGENTS.md
  in the same session that discovers them. Rediscovery is not verification;
  it is a missing artifact. Also logged: probes of third-party payloads must
  survive the exception that hides them (`fixtures=0` masked a TypeError for
  one full iteration), so broad `except` around parse loops is itself a defect.