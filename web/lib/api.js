export const BRL = (c) =>
  (c / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/** Idempotency id for one cash operation, so a double-click is a replay. */
export const newDepositId = () =>
  (globalThis.crypto && globalThis.crypto.randomUUID
    ? globalThis.crypto.randomUUID()
    : String(Date.now()) + Math.random().toString(16).slice(2));

/** Millis before an in-flight request is abandoned. */
export const REQUEST_TIMEOUT_MS = 8000;
export const PAYMENT_TIMEOUT_MS = 30000;

/** Player session, stored in one of the two browser stores.
 *
 * "Lembrar de mim" decides which: checked means localStorage, so the player
 * stays logged in across browser restarts; unchecked means sessionStorage,
 * which dies with the tab. Both are read on boot, sessionStorage first, so a
 * non-remembered login always wins over an older remembered one.
 *
 * The session is `{player_id, token}`. The token is the credential: the server
 * derives the player from it (decision 0069), so an entry without one is a
 * pre-0069 leftover and is dropped — that player simply logs in again. A
 * token the server no longer accepts is dropped by the boot refresh. */
export const PLAYER_KEY = "casa-player";

/** The player session travels on its own header, not `Authorization`: the
 * owner can be logged into the painel and the storefront at the same time. */
export const PLAYER_TOKEN_HEADER = "X-Player-Token";

const PLAYER_STORES = ["sessionStorage", "localStorage"];

function playerStore(name) {
  if (typeof window === "undefined") return null;
  try {
    const store = window[name];
    const probe = "__casa_probe__";
    store.setItem(probe, "1");
    store.removeItem(probe);
    return store;
  } catch (e) {
    return null;
  }
}

function readPlayer(store) {
  try {
    const raw = store.getItem(PLAYER_KEY);
    const session = raw ? JSON.parse(raw) : null;
    return session && session.player_id && session.token ? session : null;
  } catch (e) {
    return null;
  }
}

export function getPlayerSession() {
  for (const name of PLAYER_STORES) {
    const store = playerStore(name);
    const session = store && readPlayer(store);
    if (session) return session;
  }
  return null;
}

export function setPlayerSession(session, { remember = true } = {}) {
  const primary = remember ? "localStorage" : "sessionStorage";
  const secondary = remember ? "sessionStorage" : "localStorage";
  const clear = (name) => {
    const store = playerStore(name);
    try {
      if (store) store.removeItem(PLAYER_KEY);
    } catch (e) {
      /* nothing to clear */
    }
  };
  if (!session || !session.player_id || !session.token) {
    clear("localStorage");
    clear("sessionStorage");
    return;
  }
  // Drop the other copy first: a remembered id must never outlive a
  // deliberate "do not remember me" login, and vice versa.
  clear(secondary);
  const store = playerStore(primary) || playerStore(secondary);
  try {
    if (store) store.setItem(PLAYER_KEY, JSON.stringify(session));
  } catch (e) {
    /* private mode: the player simply logs in again next visit */
  }
}

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
  const player = getPlayerSession();
  const controller = new AbortController();
  const timeout = /^\/api\/deposit\/(pix|crypto)$/.test(path) ? PAYMENT_TIMEOUT_MS : REQUEST_TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const r = await fetch(path, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(session ? { Authorization: "Bearer " + session.token } : {}),
        ...(player ? { [PLAYER_TOKEN_HEADER]: player.token } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    // A non-JSON body (an HTML error page, a proxy 404) must not surface as
    // "JSON.parse: unexpected character at line 1 column 1".
    const type = r.headers.get("content-type") || "";
    if (!type.includes("application/json")) {
      const error = new Error(
        `resposta inesperada do servidor (HTTP ${r.status}, ${type || "sem content-type"})`
      );
      error.status = r.status;
      throw error;
    }
    let j;
    try {
      j = await r.json();
    } catch (cause) {
      const error = new Error(`resposta inválida do servidor (HTTP ${r.status})`);
      error.status = r.status;
      throw error;
    }
    if (!r.ok) {
      const error = new Error(j?.error || "HTTP " + r.status);
      error.status = r.status;
      throw error;
    }
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
