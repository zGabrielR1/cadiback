/**
 * The operator's Better Auth server — host copy of
 * `foundry/templates/betterauth/server.mjs` (decision 0066).
 *
 * One loopback Node process, reached through the Python server's same-origin
 * `/api/betterauth/*` proxy. It exposes:
 *
 *   GET  /api/betterauth/providers   the credential-aware button list
 *   GET  /api/betterauth/health      readiness
 *   GET  /api/betterauth/bridge      the OAuth landing route
 *   *    /api/betterauth/*          Better Auth
 *
 * The bridge is the only call into the wallet: it reads the session, signs
 * the identity claim over the exact JSON bytes, POSTs it to the Python host,
 * and redirects the browser to `#social=<one-time token>` (or an error).
 */
import { createHmac } from "node:crypto";
import { createServer } from "node:http";
import { pathToFileURL } from "node:url";

import { createAuth, enabledProviders, providerList } from "./auth.mjs";
import { loadLocalAuthEnv } from "./local-env.mjs";

const BASE_PATH = "/api/betterauth";

function present(value) {
  return typeof value === "string" && value.trim() !== "";
}

function allowedOrigins(env) {
  const list = String(env.BETTER_AUTH_TRUSTED_ORIGINS || "")
    .split(/[,\s]+/)
    .map((part) => part.trim())
    .filter(Boolean);
  if (present(env.BETTER_AUTH_URL)) {
    list.push(env.BETTER_AUTH_URL.replace(/\/$/, ""));
  }
  return [...new Set(list)];
}

function originAllowed(value, allowed) {
  try {
    return allowed.includes(new URL(value).origin);
  } catch {
    return false;
  }
}

function sendJson(res, status, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": String(body.length),
    "cache-control": "no-store",
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > 1024 * 1024) {
        reject(new Error("request body too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function toHeaders(req) {
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (Array.isArray(value)) value.forEach((v) => headers.append(key, v));
    else if (value !== undefined) headers.set(key, value);
  }
  return headers;
}

function toWebRequest(req, url, body) {
  const init = { method: req.method, headers: toHeaders(req) };
  if (req.method !== "GET" && req.method !== "HEAD" && body.length) {
    init.body = body;
    init.duplex = "half";
  }
  return new Request(url, init);
}

async function writeResponse(res, response) {
  const headers = {};
  for (const [key, value] of response.headers.entries()) {
    if (key.toLowerCase() === "set-cookie") continue;
    headers[key] = value;
  }
  const cookies = response.headers.getSetCookie
    ? response.headers.getSetCookie()
    : [];
  if (cookies.length) headers["set-cookie"] = cookies;
  const buffer = Buffer.from(await response.arrayBuffer());
  res.writeHead(response.status, headers);
  res.end(buffer);
}

function bridgeSignature(body, secret) {
  return "sha256=" + createHmac("sha256", secret).update(body).digest("hex");
}

async function runBridge({ req, res, auth, env, url }) {
  const allowed = allowedOrigins(env);
  const fallback = allowed[0] || url.origin;
  const returnTo = url.searchParams.get("return") || fallback;
  if (!originAllowed(returnTo, allowed)) {
    sendJson(res, 400, { error: "return origin is not trusted" });
    return;
  }
  const back = new URL(returnTo).origin;
  const fail = (reason) => {
    res.writeHead(302, {
      location: `${back}/#social_error=${encodeURIComponent(reason)}`,
      "cache-control": "no-store",
    });
    res.end();
  };
  if (url.searchParams.get("error")) {
    fail(url.searchParams.get("error_description") ||
      url.searchParams.get("error"));
    return;
  }
  if (!auth) {
    fail("login social não está configurado");
    return;
  }
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (typeof value === "string") headers.set(key, value);
  }
  let session = null;
  try {
    session = await auth.api.getSession({ headers });
  } catch (err) {
    console.warn("[betterauth] bridge session read failed:", err?.message || err);
  }
  if (!session?.user) {
    fail("sessão social não encontrada");
    return;
  }
  const user = session.user;
  const subject = String(user.providerSubject || "").trim();
  const provider = String(user.providerId || "").trim();
  if (!subject || !provider) {
    fail("a conta social não informou um identificador estável");
    return;
  }
  const payload = {
    provider,
    subject,
    email: String(user.email || ""),
    email_verified: Boolean(user.emailVerified),
    name: String(user.name || ""),
    ts: Math.floor(Date.now() / 1000),
  };
  const body = Buffer.from(JSON.stringify(payload));
  const target = (env.BETTER_AUTH_BRIDGE_URL ||
    `http://127.0.0.1:${env.PORT || 8765}`).replace(/\/$/, "") +
    "/api/auth/betterauth/session";
  let answer;
  let status;
  try {
    const response = await fetch(target, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-betterauth-signature": bridgeSignature(
          body, env.BETTER_AUTH_BRIDGE_SECRET || ""),
      },
      body,
    });
    status = response.status;
    answer = await response.json().catch(() => ({}));
  } catch (err) {
    console.warn("[betterauth] bridge backend failed:", err?.message || err);
    fail("servidor de contas indisponível");
    return;
  }
  if (status !== 200 || !answer?.token) {
    fail(answer?.error || "não foi possível concluir o login social");
    return;
  }
  res.writeHead(302, {
    location: `${back}/#social=${encodeURIComponent(answer.token)}`,
    "cache-control": "no-store",
  });
  res.end();
}

export async function startAuthServer(env = loadLocalAuthEnv()) {
  const auth = await createAuth(env);
  const port = Number(env.BETTER_AUTH_INTERNAL_PORT || 3100);
  const host = env.BETTER_AUTH_INTERNAL_HOST || "127.0.0.1";
  const ids = enabledProviders(env);

  const server = createServer(async (req, res) => {
    const proto = req.headers["x-forwarded-proto"] ||
      (env.BETTER_AUTH_URL?.startsWith("http://") ? "http" : "https");
    const hostHeader = req.headers["x-forwarded-host"] || req.headers.host;
    const url = new URL(req.url || "/", `${proto}://${hostHeader || "localhost"}`);
    try {
      if (url.pathname === `${BASE_PATH}/health` ||
          url.pathname === `${BASE_PATH}/providers`) {
        sendJson(res, 200, {
          enabled: Boolean(auth),
          providers: providerList(env),
          providers_configured: ids,
        });
        return;
      }
      if (url.pathname === `${BASE_PATH}/bridge`) {
        await runBridge({ req, res, auth, env, url });
        return;
      }
      if (!auth) {
        sendJson(res, 503, { error: "login social não está configurado" });
        return;
      }
      const body = req.method === "GET" || req.method === "HEAD"
        ? Buffer.alloc(0)
        : await readBody(req);
      const response = await auth.handler(toWebRequest(req, url, body));
      await writeResponse(res, response);
    } catch (err) {
      console.error("[betterauth] request failed:", err);
      if (!res.headersSent) sendJson(res, 500, { error: "auth server error" });
      else res.end();
    }
  });

  server.listen(port, host, () => {
    console.log(`[betterauth] ${auth ? "ready" : "unconfigured"} on ` +
      `http://${host}:${port}${BASE_PATH} (${ids.join(",") || "no providers"})`);
  });
  return server;
}

const isMain = process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  startAuthServer().catch((err) => {
    console.error("[betterauth] failed to start:", err);
    process.exitCode = 1;
  });
}
