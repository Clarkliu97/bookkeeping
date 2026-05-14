import type { NextConfig } from "next";


const allowedDevOrigins = (process.env.NEXT_ALLOWED_DEV_ORIGINS ?? "192.168.1.100")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins,
};

export default nextConfig;
