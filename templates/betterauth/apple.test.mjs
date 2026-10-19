/**
 * The Apple branch, without an Apple developer account.
 *
 * Apple is the one provider whose "client secret" is not a string pasted from
 * a console: it is an ES256 JWT this process mints from the `.p8` key. A
 * malformed key or a wrong claim is only discovered at the token exchange,
 * after the player has already left for appleid.apple.com — so these checks
 * exercise the same function at boot/test time.
 */
import assert from "node:assert/strict";
import { generateKeyPairSync } from "node:crypto";
import test from "node:test";

import { exportPKCS8, jwtVerify } from "jose";

import {
  appleClientSecret,
  enabledProviders,
  providerList,
} from "./auth.mjs";

const { privateKey, publicKey } = generateKeyPairSync("ec", {
  namedCurve: "P-256",
});

const env = {
  APPLE_CLIENT_ID: "br.com.example.candibet.web",
  APPLE_TEAM_ID: "TEAM123456",
  APPLE_KEY_ID: "KEY1234567",
  APPLE_PRIVATE_KEY: await exportPKCS8(privateKey),
};

test("Apple is offered only when all four values are present", () => {
  assert.deepEqual(enabledProviders(env), ["apple"]);
  assert.deepEqual(providerList(env), [{ id: "apple", label: "Apple" }]);
  for (const name of Object.keys(env)) {
    const incomplete = { ...env };
    delete incomplete[name];
    assert.deepEqual(enabledProviders(incomplete), [], name);
  }
});

test("the .p8 key may arrive with escaped newlines", async () => {
  const escaped = {
    ...env,
    APPLE_PRIVATE_KEY: env.APPLE_PRIVATE_KEY.replace(/\n/g, "\\n"),
  };
  const token = await appleClientSecret(escaped);
  assert.equal(token.split(".").length, 3);
});

test("the client secret is a signed ES256 JWT with Apple's claims", async () => {
  const token = await appleClientSecret(env);
  const { protectedHeader, payload } = await jwtVerify(token, publicKey, {
    issuer: env.APPLE_TEAM_ID,
    audience: "https://appleid.apple.com",
    subject: env.APPLE_CLIENT_ID,
  });
  assert.equal(protectedHeader.alg, "ES256");
  assert.equal(protectedHeader.kid, env.APPLE_KEY_ID);
  assert.equal(payload.iss, env.APPLE_TEAM_ID);
  assert.equal(payload.sub, env.APPLE_CLIENT_ID);
  assert.equal(payload.aud, "https://appleid.apple.com");
  // Apple's own limit is six months; stay below it.
  assert.equal(payload.exp - payload.iat, 180 * 24 * 60 * 60);
  assert.ok(payload.exp - Math.floor(Date.now() / 1000) > 170 * 24 * 60 * 60);
});
