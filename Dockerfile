# candibet — single-container deploy for a Python host (Render/Fly/Koyeb/Railway).
#
# One process serves everything on one port: the Python operator backend
# (`demo.server`) answers the API and serves the static storefront export
# (`web/out`) itself — no reverse proxy, no Cloudflare Worker, no tunnel.
#
#   docker build -t candibet .
#   docker run -p 8080:8080 candibet
#
# Postgres identity and sessions require the Python dependencies below.
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

# --- stage 1b: the Better Auth server's dependencies ---------------------------
# Better Auth is a TypeScript library, so social login runs in a small Node
# process beside the Python server rather than inside it (decision 0066). Its
# modules are installed here, where npm exists, and copied into the runtime.
FROM node:22-slim AS authdeps

ENV NODE_ENV=production
WORKDIR /auth
COPY auth-server/package.json auth-server/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund

# --- stage 2: the runtime -----------------------------------------------------
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    OPERATOR_DATA_DIR=/data \
    NODE_ENV=production

WORKDIR /app

# Keep runtime database dependencies in the image, independently of the
# developer's environment. The durable identity path fails closed without them.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Node for the auth sidecar. Better Auth's dependency graph needs Node >= 22
# (Kysely pins that floor) and Debian's nodejs is older, so install the official
# Node 22 tarball, pinned and checksum-verified. `linux-x64` matches Render's
# builders; a source-build on another architecture needs the matching tarball.
ARG NODE_VERSION=22.23.3
ARG NODE_SHA256=df450af89261115ef9f9e3830c3eeb2cc9213b63c720b1af623cb5dcbe2e02de
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
 && curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" \
 && echo "${NODE_SHA256}  node-v${NODE_VERSION}-linux-x64.tar.xz" | sha256sum -c - \
 && tar -xJf "node-v${NODE_VERSION}-linux-x64.tar.xz" -C /usr/local --strip-components=1 \
 && rm "node-v${NODE_VERSION}-linux-x64.tar.xz" \
 && node --version \
 && rm -rf /var/lib/apt/lists/*

# the backend, the provider catalog it reads, and the built storefront
COPY frame/ ./frame/
COPY demo/ ./demo/
COPY probes/ ./probes/
# foundry: the vendored kit modules (stdlib only). Copied rather than installed
# so the repository + this Dockerfile remain the whole build (decisions/0047).
COPY foundry/ ./foundry/
# the auth server: source plus the dependencies built above (never the host's
# node_modules — .dockerignore keeps them out of the context)
COPY auth-server/ ./auth-server/
COPY --from=authdeps /auth/node_modules ./auth-server/node_modules
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

# Two processes, one public port: the Python server answers everything and
# proxies /api/betterauth/* to the loopback Node auth server. The `&` sidecar
# is deliberately best-effort — if it fails to start, the site stays up and
# the social buttons disappear (the auth server reports itself disabled).
CMD ["sh", "-c", "node /app/auth-server/server.mjs & exec python3 -m demo.server"]
