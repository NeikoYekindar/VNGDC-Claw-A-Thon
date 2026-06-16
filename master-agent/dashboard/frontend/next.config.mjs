/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: { unoptimized: true },
  async rewrites() {
    const apiBase = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
    return [
      { source: "/api/:path*", destination: `${apiBase}/api/:path*` },
      { source: "/health", destination: `${apiBase}/health` },
      { source: "/ping", destination: `${apiBase}/ping` },
      { source: "/invocations", destination: `${apiBase}/invocations` }
    ];
  }
};

export default nextConfig;
