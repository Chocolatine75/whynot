/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true, poweredByHeader: false, devIndicators: false,
  // the public demo reads its bundled example at request time: ship it with every server function
  outputFileTracingIncludes: { "/**": ["./demo/**/*"] },
};
export default nextConfig;
