import type { NextConfig } from "next";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    if (!apiUrl) return [];
    return [
      {
        source: "/api/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
