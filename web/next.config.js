/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  images: { unoptimized: true },
  // `npm run dev` serves on :3000 but the API lives on the Python server.
  // Without this proxy every fetch returns Next's 404 HTML page and the
  // browser throws "JSON.parse: unexpected character at line 1 column 1".
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8765/api/:path*",
      },
    ];
  },
};
module.exports = nextConfig;
