import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

// api.js has no dependencies; load as ESM without changing Next's package mode.
const source = await readFile(new URL("./api.js", import.meta.url), "utf8");
const { api, getPlayerSession, setPlayerSession, PLAYER_TOKEN_HEADER } =
  await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));

function storage() {
  const data = new Map();
  return { getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value), removeItem: (key) => data.delete(key) };
}

test("player writes send only the token header and operation data", async (t) => {
  const original = { window: globalThis.window, fetch: globalThis.fetch };
  t.after(() => Object.assign(globalThis, original));
  globalThis.window = { localStorage: storage(), sessionStorage: storage() };
  setPlayerSession({ player_id: "p1", token: "signed-session" });
  globalThis.fetch = async (path, options) => {
    assert.equal(path, "/api/bonus");
    assert.equal(options.headers[PLAYER_TOKEN_HEADER], "signed-session");
    assert.deepEqual(JSON.parse(options.body), { kind: "welcome" });
    return Response.json({ ok: true });
  };
  assert.deepEqual(await api("POST", "/api/bonus", { kind: "welcome" }), { ok: true });
});

test("HTTP status survives API errors so expiry differs from temporary failure", async (t) => {
  const original = { window: globalThis.window, fetch: globalThis.fetch };
  t.after(() => Object.assign(globalThis, original));
  globalThis.window = { localStorage: storage(), sessionStorage: storage() };
  setPlayerSession({ player_id: "p1", token: "saved" });
  for (const status of [401, 503]) {
    globalThis.fetch = async () => Response.json({ error: "unavailable" }, { status });
    await assert.rejects(api("GET", "/api/player"), (error) =>
      error.status === status && error.message === "unavailable");
  }
  globalThis.fetch = async () => { throw new TypeError("offline"); };
  await assert.rejects(api("GET", "/api/player"), /offline/);
  assert.equal(getPlayerSession().token, "saved");
});

test("remember choice removes the other credential; logout clears both stores", (t) => {
  const original = globalThis.window;
  t.after(() => { globalThis.window = original; });
  globalThis.window = { localStorage: storage(), sessionStorage: storage() };
  setPlayerSession({ player_id: "p1", token: "old" });
  setPlayerSession({ player_id: "p2", token: "new" }, { remember: false });
  assert.equal(getPlayerSession().token, "new");
  assert.equal(window.localStorage.getItem("casa-player"), null);
  setPlayerSession(null);
  assert.equal(getPlayerSession(), null);
});
