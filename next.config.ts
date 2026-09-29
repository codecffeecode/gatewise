import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";
const apiOrigin = process.env.API_DEV_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: isDev ? `${apiOrigin}/api/:path*` : "/api/index",
      },
    ];
  },
};

export default nextConfig;
