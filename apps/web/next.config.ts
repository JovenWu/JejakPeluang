import type { NextConfig } from "next";

const config: NextConfig = {
  transpilePackages: ["@jejakpeluang/contracts"],
  async rewrites() {
    const origin = process.env.API_INTERNAL_ORIGIN ?? "http://localhost:8000";
    return [
      { source: "/api/v1/:path*", destination: `${origin}/api/v1/:path*` },
    ];
  },
};

export default config;
