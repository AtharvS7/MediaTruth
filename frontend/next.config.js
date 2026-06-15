/** @type {import('next').NextConfig} */

// ARCH-14: Fail the build loudly if production API URL is not configured.
// Without this, all API calls would silently go to http://localhost:8000
// which is unreachable from Vercel's edge, breaking every user analysis.
if (process.env.NODE_ENV === 'production' && !process.env.NEXT_PUBLIC_API_URL) {
  console.warn(
    '[MediaTruth] WARNING: NEXT_PUBLIC_API_URL is not set. ' +
    'API calls will fall back to http://localhost:8000 which will fail in production. ' +
    'Set NEXT_PUBLIC_API_URL in your Vercel dashboard or environment.'
  );
}

const nextConfig = {
  reactStrictMode: true,
  // DEPLOY-03: Required for Docker standalone builds (frontend/Dockerfile)
  // Next.js only generates .next/standalone when this is explicitly set
  output: 'standalone',
  images: {
    remotePatterns: [],
  },
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
  // Security headers
  async headers() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob:",
              `connect-src 'self' ${apiUrl} https://*.supabase.co wss://*.supabase.co`,
              "frame-ancestors 'none'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
