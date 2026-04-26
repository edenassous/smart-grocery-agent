/** @type {import('next').NextConfig} */
const nextConfig = {
  // proxy לבקשות API ל-FastAPI backend
  async rewrites() {
    return [
      { source: '/api/:path*', destination: 'http://localhost:8000/api/:path*' },
    ];
  },
};

export default nextConfig;
