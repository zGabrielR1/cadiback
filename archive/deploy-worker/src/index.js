/**
 * cadibet — Cloudflare Worker front for the hobby betting platform.
 *
 * Two responsibilities:
 *   1. Serve the static Next.js export (`../web/out`) from Cloudflare's edge.
 *   2. Proxy the dynamic surface the export cannot serve on its own — the
 *      wallet/API (`/api/*`), the publisher game proxy (`/g/*`), the RGS
 *      interposition (`/rgs/*`), and the root-level requests an embedded game
 *      client spawns — to the Python operator backend named by
 *      `env.BACKEND_ORIGIN`.
 *
 * Why the `Origin` header is dropped on the way out: the Python backend gates
 * writes on a same-origin check (`Handler._same_origin`) comparing `Origin`
 * against its own `Host`. Behind a proxy those never match, so every write
 * would be refused. The Worker hop is the trust boundary — the browser talks
 * to us, we talk to the backend — so the backend sees a clean, header-less
 * request exactly as it would from a same-origin caller.
 */

const API_PREFIX = "/api/";
const GAME_PREFIX = "/g/";
const RGS_PREFIX = "/rgs/";

/** A publisher-proxy session cookie, set by the game document the backend
 * serves (`Demo._serve_game`). Its presence marks a request the embedded
 * game client spawned on our own origin — see `Demo._serve_publisher_root`. */
const SESSION_COOKIE = /(?:^|;\s*)(proxy_host|proxy_game|proxy_provider)=/;

/** Routes the static export cannot answer and must always be proxied. */
function isDynamic(pathname) {
  return (
    pathname.startsWith(API_PREFIX) ||
    pathname.startsWith(GAME_PREFIX) ||
    pathname.startsWith(RGS_PREFIX)
  );
}

/** True when the request carries a live publisher-game session. */
function hasGameSession(request) {
  return SESSION_COOKIE.test(request.headers.get("cookie") || "");
}

/** The backend cannot see our hostname, so it is told ours explicitly; the
 * game proxy builds absolute asset URLs from this. */
function forwardedHeaders(request) {
  const headers = new Headers(request.headers);
  headers.set("X-Forwarded-Host", new URL(request.url).host);
  headers.set("X-Forwarded-Proto", new URL(request.url).protocol.replace(":", ""));
  // Strip the browser's origin/site hints: the backend's same-origin gate
  // compares them against a host it can never match behind a proxy.
  headers.delete("origin");
  headers.delete("referer");
  headers.delete("host");
  return headers;
}

/** Forward one request to the Python backend, preserving status, headers
 * and body. */
function proxy(request, env, url) {
  const origin = String(env.BACKEND_ORIGIN || "").replace(/\/+$/, "");
  if (!origin) {
    return Response.json(
      {
        error: "backend not configured",
        hint: "deploy with --var BACKEND_ORIGIN:https://<backend-host>",
      },
      { status: 503 }
    );
  }

  const target = new URL(origin + url.pathname + url.search);
  const body = ["GET", "HEAD"].includes(request.method)
    ? undefined
    : request.body;
  const proxied = new Request(target, {
    method: request.method,
    headers: forwardedHeaders(request),
    body,
    redirect: "manual",
  });

  return fetch(proxied);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (isDynamic(url.pathname)) {
      return proxy(request, env, url);
    }

    // Everything else is the storefront or its assets. A real asset wins
    // outright. A miss must NOT become the whole site: behind a naive
    // single-page-app fallback, a root-level request the embedded game client
    // spawned (Pragmatic Play's Unity client, Spribe's launcher) returns
    // `index.html`, so the game frame renders the storefront and the player
    // re-opens the game forever. A miss (>= 400: 404, or 405 for a non-GET)
    // that carries the session cookie goes to the backend instead, which
    // proxies it to the publisher or 404s.
    const asset = await env.ASSETS.fetch(request);
    if (asset.status < 400 || !hasGameSession(request)) {
      return asset;
    }
    return proxy(request, env, url);
  },
};
