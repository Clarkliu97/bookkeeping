import { headers } from "next/headers";


const DEFAULT_API_PORT = process.env.NEXT_PUBLIC_API_PORT ?? "8000";


function stripTrailingSlash(value: string) {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}


function isLoopbackHost(hostname: string) {
  return hostname === "localhost" || hostname === "127.0.0.1";
}


function canUseExplicitBaseUrl(explicitBaseUrl: string, currentHostname: string) {
  try {
    const parsed = new URL(explicitBaseUrl);
    if (isLoopbackHost(parsed.hostname) && !isLoopbackHost(currentHostname)) {
      return false;
    }
  } catch {
    return true;
  }
  return true;
}


function buildApiBaseUrl(protocol: string, hostname: string, port = DEFAULT_API_PORT) {
  const normalizedProtocol = protocol.endsWith(":") ? protocol : `${protocol}:`;
  return `${normalizedProtocol}//${hostname}:${port}`;
}


export async function getServerApiBaseUrl() {
  const explicitBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  const requestHeaders = await headers();
  const forwardedProto = requestHeaders.get("x-forwarded-proto");
  const protocol = forwardedProto ?? (process.env.NODE_ENV === "production" ? "https" : "http");
  const forwardedHost = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:3000";
  const hostname = forwardedHost.split(":")[0];

  if (explicitBaseUrl && canUseExplicitBaseUrl(explicitBaseUrl, hostname)) {
    return stripTrailingSlash(explicitBaseUrl);
  }

  return buildApiBaseUrl(protocol, hostname);
}