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


export function resolveClientApiBaseUrl(preferredBaseUrl?: string) {
  const explicitBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (typeof window !== "undefined") {
    const browserHostname = window.location.hostname;
    const candidateBaseUrl = preferredBaseUrl || explicitBaseUrl;
    if (candidateBaseUrl && canUseExplicitBaseUrl(candidateBaseUrl, browserHostname)) {
      return stripTrailingSlash(candidateBaseUrl);
    }
    return buildApiBaseUrl(window.location.protocol, browserHostname);
  }

  const fallbackBaseUrl = preferredBaseUrl || explicitBaseUrl;
  if (fallbackBaseUrl) {
    return stripTrailingSlash(fallbackBaseUrl);
  }

  return `http://localhost:${DEFAULT_API_PORT}`;
}


export function getClientDefaultApiBaseUrl() {
  return resolveClientApiBaseUrl();
}