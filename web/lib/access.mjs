/**
 * Data-portal access (decision 0080).
 *
 * The public storefront presents itself as a sports odds site. The full
 * terminal sits behind a neutral "Central de dados" surface and a session
 * code. This is deliberately a UI restriction, not a security boundary:
 * the bundle is static and the backend keeps its existing rules.
 */

const STORAGE_KEY = "casa-data-portal";
const DEFAULT_CODE = "feed-seguro";

function memoryStore(storage) {
  if (storage) return storage;
  try {
    return typeof window !== "undefined" ? window.sessionStorage : null;
  } catch (e) {
    return null;
  }
}

export function normalizeAccessCode(value) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

export function portalCode() {
  const override =
    typeof process !== "undefined" ? process.env.NEXT_PUBLIC_DATA_ACCESS_CODE : "";
  return normalizeAccessCode(override || DEFAULT_CODE);
}

export function hasPortalAccess(storage) {
  const store = memoryStore(storage);
  if (!store) return false;
  try {
    return store.getItem(STORAGE_KEY) === "granted";
  } catch (e) {
    return false;
  }
}

export function grantPortalAccess(code, storage) {
  if (normalizeAccessCode(code) !== portalCode()) return false;
  const store = memoryStore(storage);
  if (!store) return false;
  try {
    store.setItem(STORAGE_KEY, "granted");
  } catch (e) {
    return false;
  }
  return true;
}

export function revokePortalAccess(storage) {
  const store = memoryStore(storage);
  if (!store) return;
  try {
    store.removeItem(STORAGE_KEY);
  } catch (e) {
    /* a blocked storage must not break the shell */
  }
}
