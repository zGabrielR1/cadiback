/**
 * Better Auth configuration — social sign-in only, stateless.
 *
 * This file is the reusable half of a social login: it turns a set of
 * provider credentials into a working `/api/betterauth/*` handler. The host
 * owns routes, copy and what a signed-in person may do.
 *
 * Why stateless: Better Auth can run with no database at all. Sessions and
 * the in-flight OAuth state live in signed/encrypted cookies, which means a
 * host with no Postgres (or a free instance whose disk is wiped) still gets
 * working social login. The catch is that Better Auth does not remember an
 * account between sign-ins, so the *host* must key its own accounts on the
 * provider's stable subject. That subject is carried into the session as a
 * custom user field by `mapProfileToUser` below.
 *
 * `BETTER_AUTH_URL` (or the request Host, when the URL is left blank) is the
 * public origin. A dynamic baseURL lets one instance serve several trusted
 * hosts — e.g. a Render backend and a Vercel storefront — as long as each
 * host's `/api/betterauth/callback/<provider>` is registered with the
 * provider.
 */
import { betterAuth } from "better-auth";
import { importPKCS8, SignJWT } from "jose";

export const PROVIDERS = [
  { id: "google", label: "Google" },
  { id: "facebook", label: "Facebook" },
  { id: "apple", label: "Apple" },
];

const LABELS = Object.fromEntries(PROVIDERS.map((p) => [p.id, p.label]));

function present(value) {
  return typeof value === "string" && value.trim() !== "";
}

/** Which providers have complete credentials in `env`. */
export function enabledProviders(env = process.env) {
  const ids = [];
  if (present(env.GOOGLE_CLIENT_ID) && present(env.GOOGLE_CLIENT_SECRET)) {
    ids.push("google");
  }
  if (present(env.FACEBOOK_CLIENT_ID) && present(env.FACEBOOK_CLIENT_SECRET)) {
    ids.push("facebook");
  }
  if (present(env.APPLE_CLIENT_ID) && present(env.APPLE_TEAM_ID) &&
      present(env.APPLE_KEY_ID) && present(env.APPLE_PRIVATE_KEY)) {
    ids.push("apple");
  }
  return ids;
}

/** The provider list the storefront renders: id plus a human label. */
export function providerList(env = process.env) {
  return enabledProviders(env).map((id) => ({ id, label: LABELS[id] || id }));
}

function origins(value) {
  return String(value || "")
    .split(/[,\s]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function hostOf(value) {
  try {
    return new URL(value).host;
  } catch {
    return "";
  }
}

/** Apple wants a short-lived JWT as the client secret, signed by the .p8. */
export async function appleClientSecret(env) {
  const key = String(env.APPLE_PRIVATE_KEY).replace(/\\n/g, "\n");
  const signingKey = await importPKCS8(key, "ES256");
  const now = Math.floor(Date.now() / 1000);
  // Apple rejects secrets valid for more than six months; 180 days is safe
  // and is regenerated per process start, so there is no expiry to forget.
  return new SignJWT({})
    .setProtectedHeader({ alg: "ES256", kid: env.APPLE_KEY_ID })
    .setIssuer(env.APPLE_TEAM_ID)
    .setSubject(env.APPLE_CLIENT_ID)
    .setAudience("https://appleid.apple.com")
    .setIssuedAt(now)
    .setExpirationTime(now + 180 * 24 * 60 * 60)
    .sign(signingKey);
}

/**
 * `mapProfileToUser` is the only place the provider's stable id is captured.
 * Better Auth's generated `user.id` is not the provider subject, and stateless
 * mode does not persist an account row, so the host's link key must ride the
 * session as an additional field (`providerSubject`).
 *
 * `providerSubject` is declared `input: true` in the schema because Better
 * Auth ignores mapped values for `input: false` fields. The server therefore
 * disables every client-writable user path (`disabledPaths`) so a browser can
 * never set or change it; only this callback writes it.
 */
function mapProfile(provider) {
  return (profile) => {
    const subject = String(
      profile?.sub || profile?.id || profile?.user_id || "",
    );
    // Apple only sends `email` on the first consent; Facebook may omit it.
    // A reserved `.invalid` placeholder keeps Better Auth's optional email
    // requirement satisfied without pretending it is a real inbox.
    const email = profile?.email ||
      (subject ? `${subject}@${provider}.placeholder.invalid` : "");
    return {
      providerId: provider,
      providerSubject: subject,
      email,
    };
  };
}

/** The Better Auth instance, or null when there is nothing to configure. */
export async function createAuth(env = process.env) {
  const ids = enabledProviders(env);
  if (!ids.length) return null;
  if (!present(env.BETTER_AUTH_SECRET)) return null;

  const trusted = origins(env.BETTER_AUTH_TRUSTED_ORIGINS);
  const base = env.BETTER_AUTH_URL ? env.BETTER_AUTH_URL.replace(/\/$/, "") : "";
  const hosts = [
    ...new Set([
      hostOf(base),
      ...trusted.map(hostOf),
      "localhost:*",
      "127.0.0.1:*",
    ].filter(Boolean)),
  ];

  const socialProviders = {
    google: {
      clientId: env.GOOGLE_CLIENT_ID,
      clientSecret: env.GOOGLE_CLIENT_SECRET,
      mapProfileToUser: mapProfile("google"),
    },
    facebook: {
      clientId: env.FACEBOOK_CLIENT_ID,
      clientSecret: env.FACEBOOK_CLIENT_SECRET,
      mapProfileToUser: mapProfile("facebook"),
    },
    apple: async () => ({
      clientId: env.APPLE_CLIENT_ID,
      clientSecret: await appleClientSecret(env),
      ...(present(env.APPLE_APP_BUNDLE_IDENTIFIER)
        ? { appBundleIdentifier: env.APPLE_APP_BUNDLE_IDENTIFIER }
        : {}),
      mapProfileToUser: mapProfile("apple"),
    }),
  };
  for (const id of Object.keys(socialProviders)) {
    if (!ids.includes(id)) delete socialProviders[id];
  }

  const plugins = [];
  if (present(env.BETTER_AUTH_API_KEY)) {
    // The infrastructure dashboard is optional telemetry/admin. A missing
    // package or a bad key must never take social login down, so it is
    // loaded dynamically and skipped on any failure.
    try {
      const { dash } = await import("@better-auth/infra");
      plugins.push(dash({ apiKey: env.BETTER_AUTH_API_KEY }));
    } catch (err) {
      console.warn("[betterauth] infrastructure dashboard unavailable:",
        err?.message || err);
    }
  }

  return betterAuth({
    appName: env.BETTER_AUTH_APP_NAME || "App",
    basePath: "/api/betterauth",
    ...(base
      ? {
          baseURL: {
            allowedHosts: hosts,
            protocol: "auto",
            fallback: base,
          },
        }
      : {}),
    secret: env.BETTER_AUTH_SECRET,
    trustedOrigins: [...trusted, "https://appleid.apple.com"],
    socialProviders,
    user: {
      additionalFields: {
        providerId: { type: "string", input: true, returned: true },
        providerSubject: { type: "string", input: true, returned: true },
      },
    },
    account: {
      // The host links accounts by provider:subject; Better Auth must not
      // merge two providers' identities behind its back.
      accountLinking: { enabled: false },
    },
    // Only the social rails are used. Every client-writable user path stays
    // disabled so the server-owned provider subject cannot be changed.
    disabledPaths: [
      "/sign-up/email",
      "/sign-in/email",
      "/update-user",
      "/delete-user",
      "/change-email",
      "/change-password",
      "/set-password",
      "/link-social",
      "/unlink-account",
      "/list-accounts",
    ],
    advanced: { trustedProxyHeaders: true },
    plugins,
  });
}

export { mapProfile as _mapProfile };
