/**
 * The X (Twitter) branch, without an X developer account.
 *
 * X login uses a confidential OAuth 2.0 client.
 * What can be proven without hitting x.com: the provider is offered only
 * when both values are present, its storefront label is `X` (not
 * `Twitter`), and its provider id — the one that has to match the
 * callback path — is `twitter`.
 */
import assert from "node:assert/strict";
import test from "node:test";

import { createAuth, enabledProviders, providerList } from "./auth.mjs";

const env = {
  TWITTER_CLIENT_ID: "x-oauth2-client-id-example",
  TWITTER_CLIENT_SECRET: "x-oauth2-client-secret-example",
};

test("X is offered only when both values are present, labelled X", () => {
  assert.deepEqual(enabledProviders(env), ["twitter"]);
  assert.deepEqual(providerList(env), [{ id: "twitter", label: "X" }]);
  for (const name of Object.keys(env)) {
    const incomplete = { ...env };
    delete incomplete[name];
    assert.deepEqual(enabledProviders(incomplete), [], name);
  }
});

test("a missing or blank value hides X without hiding other providers", () => {
  assert.deepEqual(
    enabledProviders({ TWITTER_CLIENT_ID: " ", TWITTER_CLIENT_SECRET: "x" }),
    [],
  );
  const mixed = {
    GOOGLE_CLIENT_ID: "g",
    GOOGLE_CLIENT_SECRET: "g",
    ...env,
  };
  assert.deepEqual(enabledProviders(mixed), ["google", "twitter"]);
});

test("X maps the API v2 envelope and requests only the configured scopes", async () => {
  const auth = await createAuth({
    ...env,
    BETTER_AUTH_SECRET: "test-secret-at-least-thirty-two-characters",
    BETTER_AUTH_URL: "http://127.0.0.1:8765",
  });
  const context = await auth.$context;
  const provider = context.socialProviders.find((p) => p.id === "twitter");
  assert.deepEqual(await provider.options.mapProfileToUser({
    data: { id: "12345", name: "X User" },
  }), {
    providerId: "twitter",
    providerSubject: "12345",
    email: "12345@twitter.placeholder.invalid",
  });
  const url = await provider.createAuthorizationURL({
    state: "test-state", codeVerifier: "test-verifier",
    redirectURI: "http://127.0.0.1:8765/api/betterauth/callback/twitter",
  });
  assert.deepEqual(new Set(new URL(url).searchParams.get("scope").split(" ")),
    new Set(["tweet.read", "users.read", "offline.access"]));
  assert.equal(new URL(url).searchParams.get("code_challenge_method"), "S256");
});
