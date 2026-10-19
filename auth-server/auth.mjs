/**
 * Better Auth configuration for the operator — the host copy of
 * `foundry/templates/betterauth/auth.mjs` (decision 0066).
 *
 * Social sign-in only, stateless: no database, so a free Render instance
 * whose disk resets still gets a working login. The wallet is the source of
 * truth and lives in the Python process; this server only proves who signed
 * in and hands that identity over through the signed bridge.
 *
 * Keep this file in sync with the foundry template when the generic shape
 * changes; the operator-specific part is only the app name and the env names.
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

async function appleClientSecret(env) {
  const key = String(env.APPLE_PRIVATE_KEY).replace(/\\n/g, "\n");
  const signingKey = await importPKCS8(key, "ES256");
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({})
    .setProtectedHeader({ alg: "ES256", kid: env.APPLE_KEY_ID })
    .setIssuer(env.APPLE_TEAM_ID)
    .setSubject(env.APPLE_CLIENT_ID)
    .setAudience("https://appleid.apple.com")
    .setIssuedAt(now)
    .setExpirationTime(now + 180 * 24 * 60 * 60)
    .sign(signingKey);
}

function mapProfile(provider) {
  return (profile) => {
    const subject = String(
      profile?.sub || profile?.id || profile?.user_id || "",
    );
    const email = profile?.email ||
      (subject ? `${subject}@${provider}.placeholder.invalid` : "");
    return {
      providerId: provider,
      providerSubject: subject,
      email,
    };
  };
}

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
    try {
      const { dash } = await import("@better-auth/infra");
      plugins.push(dash({ apiKey: env.BETTER_AUTH_API_KEY }));
    } catch (err) {
      console.warn("[betterauth] infrastructure dashboard unavailable:",
        err?.message || err);
    }
  }

  return betterAuth({
    appName: env.BETTER_AUTH_APP_NAME || "Candibet",
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
      accountLinking: { enabled: false },
    },
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
