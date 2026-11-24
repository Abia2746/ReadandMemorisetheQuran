import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  // The website requires a Node.js server for encrypted HttpOnly sessions.
  // Static export cannot handle dynamic sign-in/refresh/logout route handlers.
  // Capacitor packaging must use a separate, dedicated static/mobile build
  // once its authentication and payment architecture is ready.
  reactStrictMode: true,
  images: { unoptimized: true },
  poweredByHeader: false,
};
export default nextConfig;
