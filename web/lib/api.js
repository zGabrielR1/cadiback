export const BRL = (c) =>
  (c / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/** Idempotency id for one cash operation, so a double-click is a replay. */
export const newDepositId = () =>
  (globalThis.crypto && globalThis.crypto.randomUUID
    ? globalThis.crypto.randomUUID()
    : String(Date.now()) + Math.random().toString(16).slice(2));

/** Millis before an in-flight request is abandoned. */
export const REQUEST_TIMEOUT_MS = 8000;

/** Painel administrativo session: {token, username, role} in localStorage.
 * Absent for normal players — their requests then carry no Authorization
 * header and every /api/admin* route answers 401. */
export const ADMIN_KEY = "casa-admin";

export function getAdminSession() {
  try {
    const raw = window.localStorage.getItem(ADMIN_KEY);
    const session = raw ? JSON.parse(raw) : null;
    return session && session.token ? session : null;
  } catch (e) {
    return null;
  }
}

export function setAdminSession(session) {
  try {
    if (session && session.token) {
      window.localStorage.setItem(ADMIN_KEY, JSON.stringify(session));
    } else {
      window.localStorage.removeItem(ADMIN_KEY);
    }
  } catch (e) {
    /* private mode: the panel simply stays logged out */
  }
}

export async function api(method, path, body) {
  const session = getAdminSession();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const r = await fetch(path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(session ? { Authorization: "Bearer " + session.token } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    // A non-JSON body (an HTML error page, a proxy 404) must not surface as
    // "JSON.parse: unexpected character at line 1 column 1".
    const type = r.headers.get("content-type") || "";
    if (!type.includes("application/json")) {
      throw new Error(
        `resposta inesperada do servidor (HTTP ${r.status}, ${type || "sem content-type"})`
      );
    }
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "HTTP " + r.status);
    return j;
  } catch (e) {
    if (e.name === "AbortError") {
      throw new Error("tempo esgotado — tente de novo");
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}