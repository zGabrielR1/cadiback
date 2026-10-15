# candibet — single-container deploy for a Python host (Render/Fly/Koyeb/Railway).
#
# One process serves everything on one port: the Python operator backend
# (`demo.server`) answers the API and serves the static storefront export
# (`web/out`) itself — no reverse proxy, no Cloudflare Worker, no tunnel.
#
#   docker build -t candibet .
#   docker run -p 8080:8080 candibet
#
# Stdlib-only backend, so there is no pip install step.
#
# The storefront is built INSIDE the image, from source. That is what makes a
# remote host work with no help from the build machine: the deploy is the
# repository plus this file, never an artifact somebody remembered to commit.
# (The old shape copied `web/out` in, which meant every deploy depended on
# whatever machine happened to run `npm run build` last.)

# --- stage 1: the storefront --------------------------------------------------
FROM node:22-slim AS storefront

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /build

# dependencies first: they change far less often than the app does
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/next.config.js ./
COPY web/app/ ./app/
COPY web/lib/ ./lib/
COPY web/public/ ./public/
RUN npm run build

# --- stage 2: the runtime -----------------------------------------------------
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    OPERATOR_DATA_DIR=/data

WORKDIR /app

# the backend, the provider catalog it reads, and the built storefront
COPY frame/ ./frame/
COPY demo/ ./demo/
COPY probes/ ./probes/
# foundry: the vendored kit modules (stdlib only). Copied rather than installed
# so the repository + this Dockerfile remain the whole build (decisions/0047).
COPY foundry/ ./foundry/
COPY --from=storefront /build/out/ ./web/out/

# run unprivileged; /data is where the ledger, profiles and rounds live. The
# backend creates it if the host gives it no volume (free plan), which is why
# the ledger resets on each deploy there.
#
# `groupadd -f` first: Debian ships an `operator` GROUP (systemd's, GID 37), so
# `useradd operator` on python:3.14-slim fails with "group operator exists"
# and exit code 9 — the image died at exactly this line on Render, after the
# storefront had already built. `-f` makes the groupadd idempotent, and `-g`
# points the user at that group instead of trying to create it again.
RUN groupadd -f operator \
 && useradd --create-home --shell /bin/false -g operator operator \
 && mkdir -p /data && chown -R operator:operator /data /app
USER operator

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/api/health',timeout=4)"

CMD ["python3", "-m", "demo.server"]