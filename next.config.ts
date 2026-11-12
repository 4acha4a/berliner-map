import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  logging: { incomingRequests: { ignore: [/^\/api\/v1\/sectors\/identify(?:[?\/]|$)/] } },
  outputFileTracingRoot: process.cwd(),
  turbopack: { root: process.cwd() },
};
export default config;
