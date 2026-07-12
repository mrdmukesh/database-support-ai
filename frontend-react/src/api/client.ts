import type { Session } from "../models/auth";
import type { FastApiValidationIssue } from "../models/api-error";
import { API_BASE_URL } from "./config";

export const SESSION_STORAGE_KEY = "legacydb-session";
export const SESSION_EXPIRED_EVENT = "legacydb:session-expired";

export class ApiClientError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(message: string, status: number, detail?: unknown, options?: ErrorOptions) {
    super(message, options);
    this.name = "ApiClientError";
    this.status = status;
    this.detail = detail;
  }
}

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

function getStoredSession(): Session | null {
  try {
    const value = localStorage.getItem(SESSION_STORAGE_KEY);
    return value ? (JSON.parse(value) as Session) : null;
  } catch {
    return null;
  }
}

function validationMessage(issues: FastApiValidationIssue[]): string {
  return issues
    .map((issue) => {
      const location = Array.isArray(issue.loc) ? issue.loc.join(".") : "";
      return [location, issue.msg].filter(Boolean).join(": ");
    })
    .filter(Boolean)
    .join(", ");
}

function errorMessage(detail: unknown, fallback: string): string {
  if (Array.isArray(detail)) {
    return validationMessage(detail as FastApiValidationIssue[]) || fallback;
  }
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    if (typeof record.message === "string" && record.message) return record.message;
    if (typeof record.msg === "string" && record.msg) return record.msg;
    return JSON.stringify(detail);
  }
  return fallback;
}

async function readResponse(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text) as unknown;
  } catch (cause) {
    if (!response.ok) return { detail: text };
    throw new ApiClientError("Response was not valid JSON.", response.status, text, { cause });
  }
}

export async function apiRequest<T = unknown>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T | undefined> {
  const session = getStoredSession();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (session?.access_token) {
    headers.set(
      "Authorization",
      `${session.token_type || "bearer"} ${session.access_token}`,
    );
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiClientError("Network request failed.", 0, undefined, { cause });
  }

  const data = await readResponse(response);
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    const detail = data && typeof data === "object" ? (data as Record<string, unknown>).detail : data;
    throw new ApiClientError(
      errorMessage(detail, response.statusText || "Request failed"),
      response.status,
      detail,
    );
  }
  return data as T | undefined;
}
