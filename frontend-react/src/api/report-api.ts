import { API_BASE_URL } from "./config";
import { ApiClientError, SESSION_EXPIRED_EVENT, SESSION_STORAGE_KEY } from "./client";

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
  try { return decodeURIComponent(new URL(path, API_BASE_URL).pathname.split("/").pop() || "investigation_report"); }
  catch { return "investigation_report"; }
}

export function filenameFromDisposition(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback;
  const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8) { try { return decodeURIComponent(utf8[1]); } catch { return utf8[1]; } }
  return disposition.match(/filename="([^"]+)"/i)?.[1] ?? disposition.match(/filename=([^;]+)/i)?.[1]?.trim() ?? fallback;
}

export async function fetchReportArtifact(path: string, signal?: AbortSignal): Promise<ReportArtifact> {
  if (!path || !path.startsWith("/reports/")) throw new ApiClientError("Report link is unavailable.", 0);
  const token = authorization();
  if (!token) throw new ApiClientError("Authentication is required.", 401);
  let response: Response;
  try { response = await fetch(`${API_BASE_URL}${path}`, { headers: { Authorization: token }, signal }); }
  catch (cause) { throw new ApiClientError("Report download failed.", 0, undefined, { cause }); }
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    const body = await response.json().catch(() => undefined) as { detail?: unknown } | undefined;
    throw new ApiClientError(typeof body?.detail === "string" ? body.detail : response.statusText || "Report download failed.", response.status, body?.detail);
  }
  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(response.headers.get("Content-Disposition"), fallbackFilename(path)),
    contentType: response.headers.get("Content-Type") ?? "application/octet-stream",
  };
}
