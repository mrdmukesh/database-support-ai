import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Session } from "../models/auth";
import { apiRequest, SESSION_STORAGE_KEY } from "./client";

const session: Session = {
  access_token: "test-token",
  token_type: "bearer",
  user: {
    id: "USER-1",
    organization_id: "ORG-1",
    email: "admin@example.com",
    full_name: "Admin",
    role: "organization_admin",
    is_active: true,
  },
};

function respond(body: string | null, status = 200, statusText = "OK") {
  return new Response(body, {
    status,
    statusText,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiRequest", () => {
  beforeEach(() => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  });

  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it("returns successful JSON and sends the stored session header", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(respond('{"status":"ok"}'));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiRequest<{ status: string }>("/health")).resolves.toEqual({ status: "ok" });
    const request = fetchMock.mock.calls[0];
    const headers = new Headers(request[1]?.headers);
    expect(request[0]).toBe("http://127.0.0.1:8001/health");
    expect(headers.get("Authorization")).toBe("bearer test-token");
  });

  it("returns undefined for an empty response", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(respond(null, 204, "No Content")));

    await expect(apiRequest("/workspaces/WS-1", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("normalizes FastAPI validation errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        respond(
          JSON.stringify({ detail: [{ loc: ["body", "question"], msg: "Field required", type: "missing" }] }),
          422,
          "Unprocessable Entity",
        ),
      ),
    );

    await expect(apiRequest("/chat/ask", { method: "POST", body: {} })).rejects.toMatchObject({
      name: "ApiClientError",
      status: 422,
      message: "body.question: Field required",
    });
  });

  it("normalizes server errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(respond('{"detail":"Report generation failed"}', 500, "Server Error")),
    );

    await expect(apiRequest("/chat/ask")).rejects.toMatchObject({
      status: 500,
      message: "Report generation failed",
    });
  });

  it("rejects an invalid successful JSON response", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockResolvedValue(respond("not-json")));

    await expect(apiRequest("/health")).rejects.toEqual(
      expect.objectContaining({
        name: "ApiClientError",
        status: 200,
        message: "Response was not valid JSON.",
      }),
    );
  });

  it("normalizes network failures", async () => {
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(new TypeError("offline")));

    await expect(apiRequest("/health")).rejects.toMatchObject({
      status: 0,
      message: "Network request failed.",
    });
  });

  it("clears the stored session on HTTP 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(respond('{"detail":"Token expired"}', 401, "Unauthorized")),
    );

    await expect(apiRequest("/admin/summary")).rejects.toMatchObject({
      status: 401,
      message: "Token expired",
    });
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });
});
