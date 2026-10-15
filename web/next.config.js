/** @type {import('next').NextConfig} */
const BACKEND_URL = (process.env.BACKEND_URL || "http://127.0.0.1:8765").replace(
  /\/$/,
  ""
);
// On Vercel (or with NEXT_OUTPUT=server) the storefront runs as a server app
// whose rewrites proxy the backend, keeping every fetch relative and
// same-origin: no api.js changes, no CORS surface on the money paths, and the
// game iframes/postMessage/cookies keep working unchanged (decision 0049).
// Everywhere else — local dev, the Docker image, verify.py's web/out check —
// the static export is the build, exactly as before.
const SERVER_OUTPUT =
  process.env.NEXT_OUTPUT === "server" || process.env.VERCEL === "1";

const nextConfig = {
  ...(SERVER_OUTPUT ? {} : { output: "export" }),
  images: { unoptimized: true },
  // `npm run dev` serves on :3000 but the API lives on the Python server.
  // Without this proxy every fetch returns Next's 404 HTML page and the
  // browser throws "JSON.parse: unexpected character at line 1 column 1".
  async rewrites() {
    const api = {
      source: "/api/:path*",
      destination: BACKEND_URL + "/api/:path*",
    };
    if (!SERVER_OUTPUT) return [api];
    // Server mode proxies the game seams too: /g/ serves proxied publisher
    // content and /rgs/ answers its own preflight, so both must reach the
    // backend rather than Vercel static.
    return [
      api,
      { source: "/g/:path*", destination: BACKEND_URL + "/g/:path*" },
      { source: "/rgs/:path*", destination: BACKEND_URL + "/rgs/:path*" },
    ];
  },
};
module.exports = nextConfig;
