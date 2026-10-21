import { readFileSync } from "node:fs";
import { parseEnv } from "node:util";

/** Production environment wins; .env.local overrides the legacy auth file. */
export function loadLocalAuthEnv(environ = process.env, root = new URL("../", import.meta.url)) {
  const values = {};
  for (const name of [".env.betterauth", ".env.local"]) {
    try {
      Object.assign(values, parseEnv(readFileSync(new URL(name, root), "utf8")));
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
  return { ...values, ...environ };
}
