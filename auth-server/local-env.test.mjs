import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { loadLocalAuthEnv } from "./local-env.mjs";

test("local auth credentials override the legacy file; exported values win", () => {
  const directory = mkdtempSync(join(tmpdir(), "operator-auth-env-"));
  try {
    const root = pathToFileURL(directory + "/");
    assert.deepEqual(loadLocalAuthEnv({ NODE_ENV: "test" }, root), { NODE_ENV: "test" });
    writeFileSync(join(directory, ".env.betterauth"), "GOOGLE_CLIENT_ID=legacy\nBETTER_AUTH_SECRET=retained\n");
    writeFileSync(join(directory, ".env.local"), 'GOOGLE_CLIENT_ID=local\nGOOGLE_CLIENT_SECRET="local-secret"\n');
    assert.deepEqual(loadLocalAuthEnv({ GOOGLE_CLIENT_SECRET: "exported" }, root), {
      GOOGLE_CLIENT_ID: "local", GOOGLE_CLIENT_SECRET: "exported", BETTER_AUTH_SECRET: "retained",
    });
  } finally {
    rmSync(directory, { recursive: true });
  }
});
