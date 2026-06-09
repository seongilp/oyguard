import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app so Turbopack doesn't pick up
  // unrelated lockfiles found higher in the filesystem.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
