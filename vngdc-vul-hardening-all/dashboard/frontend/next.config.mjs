/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: { unoptimized: true },
  // /api/* -> FastAPI on :8000 (both dev and production)
  async rewrites() {
    const apiBase = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
    return [
      { source: "/api/:path*", destination: `${apiBase}/api/:path*` },
      { source: "/ping", destination: `${apiBase}/ping` },
    ];
  },
};

export default nextConfig;
