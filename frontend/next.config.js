/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Tier 2 #27: standalone produces a minimal self-contained server
  // (`.next/standalone/server.js`) so the runtime image ships only the traced
  // deps, not the entire node_modules tree.
  output: "standalone",
};

module.exports = nextConfig;
