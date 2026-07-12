export interface BrowserLocation {
  hostname: string;
}

const LOCAL_API_BASE_URL = "http://127.0.0.1:8001";
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);

function normalizeConfiguredUrl(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";

  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    throw new Error("VITE_API_BASE_URL must be an absolute HTTP or HTTPS URL.");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("VITE_API_BASE_URL must use HTTP or HTTPS.");
  }
  if (url.search || url.hash) {
    throw new Error("VITE_API_BASE_URL must not include a query string or fragment.");
  }
  return url.toString().replace(/\/+$/, "");
}

export function resolveApiBaseUrl(
  configuredValue: string | undefined,
  location: BrowserLocation,
): string {
  const configuredUrl = normalizeConfiguredUrl(configuredValue ?? "");
  if (configuredUrl) return configuredUrl;
  return LOCAL_HOSTS.has(location.hostname.toLowerCase()) ? LOCAL_API_BASE_URL : "";
}

export const API_BASE_URL = resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL, window.location);
