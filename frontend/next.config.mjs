
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Nothing uses next/image. This turns /_next/image off, and with it the advisories in that API.
  images: { unoptimized: true },
};

export default nextConfig;