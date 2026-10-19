/**
 * Start a social sign-in from any browser, with no framework dependency.
 *
 * Better Auth's own client works too; this helper exists so a host that does
 * not want the client bundle can still use the same two-step contract:
 *
 *   POST /api/betterauth/sign-in/social  ->  { url } + the OAuth state cookie
 *   window.location.assign(url)
 *
 * `callbackURL` points at the bridge, which finishes the flow and returns the
 * browser to `returnOrigin` with `#social=<one-time token>` in the hash.
 */
export async function socialSignIn(provider, options = {}) {
  const returnOrigin = options.returnOrigin ||
    (typeof window !== "undefined" ? window.location.origin : "");
  const callbackURL = options.callbackPath || "/api/betterauth/bridge";
  const target = new URL(callbackURL, "http://placeholder.local");
  target.searchParams.set("return", returnOrigin);
  const response = await fetch("/api/betterauth/sign-in/social", {
    method: "POST",
    credentials: "same-origin",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      provider,
      callbackURL: target.pathname + target.search,
    }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || !body.url) {
    throw new Error(body.message || body.error || `login failed (HTTP ${response.status})`);
  }
  window.location.assign(body.url);
}
