import type { Session } from "../models/auth";
import type { DocumentSummary, DocumentUploadFields } from "../models/document";
import { API_BASE_URL } from "./config";
import {
  ApiClientError,
  apiRequest,
  SESSION_EXPIRED_EVENT,
  SESSION_STORAGE_KEY,
} from "./client";

export const DOCUMENT_ACCEPT = ".pdf,.docx,.txt,.csv,.sql,.md,.zip";
export const DOCUMENT_MAX_SIZE_BYTES = 25 * 1024 * 1024;
const allowedExtensions = new Set(DOCUMENT_ACCEPT.split(","));

export function validateDocumentFile(file: File): void {
  const dot = file.name.lastIndexOf(".");
  const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
  if (!allowedExtensions.has(extension)) {
    throw new Error(`Unsupported file extension: ${extension || "<none>"}`);
  }
  if (file.size <= 0) throw new Error("Uploaded file must not be empty");
  if (file.size > DOCUMENT_MAX_SIZE_BYTES) throw new Error("Uploaded file exceeds maximum size");
}

function storedSession(): Session | null {
  try {
    const value = localStorage.getItem(SESSION_STORAGE_KEY);
    return value ? (JSON.parse(value) as Session) : null;
  } catch {
    return null;
  }
}

export async function listDocuments(
  organizationId: string,
  workspaceId?: string,
  signal?: AbortSignal,
): Promise<DocumentSummary[]> {
  const query = new URLSearchParams({ organization_id: organizationId });
  if (workspaceId) query.set("workspace_id", workspaceId);
  return (await apiRequest<DocumentSummary[]>(`/documents?${query}`, { signal })) ?? [];
}

export async function uploadDocument(
  fields: DocumentUploadFields,
  signal?: AbortSignal,
): Promise<DocumentSummary> {
  validateDocumentFile(fields.file);
  const body = new FormData();
  body.append("organization_id", fields.organization_id);
  body.append("workspace_id", fields.workspace_id);
  body.append("title", fields.title);
  body.append("file", fields.file);
  const session = storedSession();
  const headers = new Headers();
  if (session?.access_token) {
    headers.set("Authorization", `${session.token_type || "bearer"} ${session.access_token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/documents/upload`, { method: "POST", headers, body, signal });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiClientError("Network request failed.", 0, undefined, { cause });
  }
  const text = await response.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : undefined;
  } catch {
    data = text;
  }
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    const detail = data && typeof data === "object" ? (data as Record<string, unknown>).detail : data;
    const message = typeof detail === "string" ? detail : response.statusText || "Upload failed";
    throw new ApiClientError(message, response.status, detail);
  }
  if (!data || typeof data !== "object") {
    throw new ApiClientError("Document upload returned an invalid response.", response.status, data);
  }
  return data as DocumentSummary;
}
