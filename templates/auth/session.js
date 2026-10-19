/* Browser session storage with a "remember me" choice.
 *
 * Checked   -> localStorage    (survives a browser restart)
 * Unchecked -> sessionStorage  (dies with the tab)
 *
 * Both are read on boot, sessionStorage first: a deliberate non-remembered
 * login must win over an older remembered one. Writes clear the other store
 * first for the same reason. Private mode can make either store throw; the
 * helpers degrade to "log in again next visit" instead of breaking the page.
 *
 * Copy this into the host's client code. It is a template, not a package.
 */
export const SESSION_KEY = "app-session";

const STORES = ["sessionStorage", "localStorage"];

function store(name) {
  if (typeof window === "undefined") return null;
  try {
    const candidate = window[name];
    const probe = "__session_probe__";
    candidate.setItem(probe, "1");
    candidate.removeItem(probe);
    return candidate;
  } catch (e) {
    return null;
  }
}

function read(handle) {
  try {
    const raw = handle.getItem(SESSION_KEY);
    const value = raw ? JSON.parse(raw) : null;
    return value && typeof value === "object" ? value : null;
  } catch (e) {
    return null;
  }
}

export function readSession() {
  for (const name of STORES) {
    const handle = store(name);
    const value = handle && read(handle);
    if (value) return value;
  }
  return null;
}

export function writeSession(value, { remember = true } = {}) {
  const primary = remember ? "localStorage" : "sessionStorage";
  const secondary = remember ? "sessionStorage" : "localStorage";
  const clear = (name) => {
    const handle = store(name);
    try {
      if (handle) handle.removeItem(SESSION_KEY);
    } catch (e) {
      /* nothing to clear */
    }
  };
  if (!value) {
    clear("localStorage");
    clear("sessionStorage");
    return;
  }
  clear(secondary);
  const handle = store(primary) || store(secondary);
  try {
    if (handle) handle.setItem(SESSION_KEY, JSON.stringify(value));
  } catch (e) {
    /* private mode: the visitor simply signs in again next visit */
  }
}

export function clearSession() {
  writeSession(null);
}
