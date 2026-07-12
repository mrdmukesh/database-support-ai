import { API_BASE_URL } from "./config";
import { ApiClientError, SESSION_EXPIRED_EVENT, SESSION_STORAGE_KEY, sanitizeErrorMessage } from "./client";

export interface ReportArtifact { blob: Blob; filename: string; contentType: string }

export const REPORT_LINK_KEYS = ["html", "pdf", "docx", "xlsx", "audit_html", "audit_pdf", "audit_docx", "audit_xlsx", "ai_trace"] as const;
export type ReportLinkKey = typeof REPORT_LINK_KEYS[number];

function authorization(): string | null {
  try {
    const session = JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) ?? "null") as { access_token?: string; token_type?: string } | null;
    return session?.access_token ? `${session.token_type || "bearer"} ${session.access_token}` : null;
  } catch { return null; }
}

function fallbackFilename(path: string): string {
  try { return safeFilename(decodeURIComponent(new URL(path, window.location.origin).pathname.split("/").pop() || "investigation_report")); }
  catch { return "investigation_report"; }
}

export function safeFilename(value: string): string {
  const basename = value.replace(/\\/g, "/").split("/").pop() ?? "";
  const invalidFilenameCharacter = /[<>:"|?*]/;
  const cleaned = basename
    .split("")
    .map((char) => {
      const code = char.charCodeAt(0);
      return code <= 0x1f || code === 0x7f || invalidFilenameCharacter.test(char) ? "_" : char;
    })
    .join("")
    .replace(/^\.+/, "")
    .trim();
  return cleaned || "investigation_report";
}

export function filenameFromDisposition(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8) {
    try {
      return safeFilename(decodeURIComponent(utf8[1]));
    } catch {
      return safeFilename(utf8[1]);
    }
  }

  const quoted = disposition.match(/filename="([^"]*)"/i)?.[1];
  if (quoted !== undefined) {
    return safeFilename(quoted);
  }

  const unquoted = disposition.match(/filename=([^;]+)/i)?.[1]?.trim();
  if (unquoted !== undefined) {
    const stripped = unquoted.replace(/^"(.*)"$/s, "$1");
    return safeFilename(stripped);
  }

  return safeFilename(fallback);
}

export function resolveReportUrl(path: string): string {
  if (!path || !path.startsWith("/reports/") || path.includes("\\")) throw new ApiClientError("Report link is unavailable.", 0);
  const base=API_BASE_URL || window.location.origin; const url=new URL(path, base);
  if (url.origin !== new URL(base, window.location.origin).origin || !url.pathname.startsWith("/reports/") || url.hash || url.search) throw new ApiClientError("Report link is unavailable.", 0);
  return url.toString();
}

export async function fetchReportArtifact(path: string, signal?: AbortSignal): Promise<ReportArtifact> {
  const reportUrl=resolveReportUrl(path);
  const token = authorization();
  if (!token) throw new ApiClientError("Authentication is required.", 401);
  let response: Response;
  try { response = await fetch(reportUrl, { headers: { Authorization: token }, signal }); }
  catch (cause) { throw new ApiClientError("Report download failed.", 0, undefined, { cause }); }
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    const body = await response.json().catch(() => undefined) as { detail?: unknown } | undefined;
    const message=typeof body?.detail === "string" ? body.detail : response.statusText || "Report download failed.";
    throw new ApiClientError(sanitizeErrorMessage(message), response.status, undefined);
  }
  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(response.headers.get("Content-Disposition"), fallbackFilename(path)),
    contentType: response.headers.get("Content-Type") ?? "application/octet-stream",
  };
}
