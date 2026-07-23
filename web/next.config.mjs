const DEFAULT_ALLOWED_DEV_ORIGINS = "192.168.1.100-253,web";

function isValidOctet(value) {
  return Number.isInteger(value) && value >= 0 && value <= 255;
}

function expandAllowedDevOrigin(origin) {
  const trimmedOrigin = origin.trim();

  if (!trimmedOrigin) {
    return [];
  }

  const shortRangeMatch = trimmedOrigin.match(/^(\d{1,3}\.\d{1,3}\.\d{1,3})\.(\d{1,3})-(\d{1,3})$/);

  if (!shortRangeMatch) {
    return [trimmedOrigin];
  }

  const [, prefix, rawStart, rawEnd] = shortRangeMatch;
  const start = Number(rawStart);
  const end = Number(rawEnd);

  if (!isValidOctet(start) || !isValidOctet(end) || start > end) {
    throw new Error(`Invalid NEXT_ALLOWED_DEV_ORIGINS range: ${trimmedOrigin}`);
  }

  return Array.from({ length: end - start + 1 }, (_, index) => `${prefix}.${start + index}`);
}

const allowedDevOriginsValue = typeof process !== "undefined" && typeof process.env.NEXT_ALLOWED_DEV_ORIGINS === "string"
  ? process.env.NEXT_ALLOWED_DEV_ORIGINS
  : DEFAULT_ALLOWED_DEV_ORIGINS;

const allowedDevOrigins = allowedDevOriginsValue
  .split(",")
  .flatMap(expandAllowedDevOrigin);

const nextConfig = {
  reactStrictMode: true,
  allowedDevOrigins,
};

export default nextConfig;
