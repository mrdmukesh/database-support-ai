import { afterEach, describe, expect, it, vi } from "vitest";
import { SESSION_STORAGE_KEY } from "./client";
import { fetchReportArtifact, filenameFromDisposition } from "./report-api";
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });
describe("report API", () => {
  it("preserves authorization, blobs, backend filenames and content type", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ access_token: "token", token_type: "Bearer" }));
    const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(["pdf"]), { headers: { "Content-Disposition": 'attachment; filename="backend.pdf"', "Content-Type": "application/pdf" } }));
    vi.stubGlobal("fetch", fetchMock);
    const artifact = await fetchReportArtifact("/reports/INV-1/report.pdf");
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe("Bearer token");
    expect(artifact.filename).toBe("backend.pdf"); expect(artifact.contentType).toBe("application/pdf");
  });
  it("rejects unavailable links and unauthorized requests without fetching", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    await expect(fetchReportArtifact("")).rejects.toMatchObject({ status: 0 });
    await expect(fetchReportArtifact("/reports/INV/a.pdf")).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("preserves RFC filename values with safe fallbacks", () => {
    expect(filenameFromDisposition("attachment; filename*=UTF-8''audit%20report.pdf", "fallback")).toBe("audit report.pdf");
    expect(filenameFromDisposition(null, "fallback.pdf")).toBe("fallback.pdf");
  });
});
