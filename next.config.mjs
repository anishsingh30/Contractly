/** @type {import('next').NextConfig} */
const rawBackend = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const backendDestination = rawBackend.replace(/\/api\/v1\/?$/, '').replace(/\/+$/, '');

const nextConfig = {
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendDestination}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
