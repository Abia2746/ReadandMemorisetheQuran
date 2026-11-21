import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  // Static bundle also works inside Capacitor, with FastAPI on a separate origin.
  output: "export",
  reactStrictMode: true,
  images: { unoptimized: true },
  poweredByHeader: false,
};
export default nextConfig;
