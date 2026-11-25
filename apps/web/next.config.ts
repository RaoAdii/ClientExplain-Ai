import type { NextConfig } from "next";

const serverAuthMode = process.env.AUTH_MODE;
const publicAuthMode = process.env.NEXT_PUBLIC_AUTH_MODE;
if (serverAuthMode && publicAuthMode && serverAuthMode !== publicAuthMode) {
  throw new Error("AUTH_MODE and NEXT_PUBLIC_AUTH_MODE must match.");
}
if (process.env.NODE_ENV === "production" && (serverAuthMode === "development" || publicAuthMode === "development")) {
  throw new Error("Development authentication cannot be used in a production build.");
}

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_ACCEPTANCE_INSTANCE === "1"
    ? process.env.NODE_ENV === "production" ? ".next-acceptance-build" : ".next-acceptance"
    : ".next",
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};
export default nextConfig;
