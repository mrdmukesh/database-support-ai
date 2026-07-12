import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExecutiveSummarySection } from "./components/investigation/ExecutiveSummarySection";
import { ApiClientError, SESSION_STORAGE_KEY, sanitizeErrorMessage } from "./api/client";
import { fetchReportArtifact, filenameFromDisposition, resolveReportUrl, safeFilename } from "./api/report-api";

describe("frontend security regressions", () => {
  it("renders legacy assistant markup as text without executable DOM", () => {
    const attack='<img src=x onerror="globalThis.compromised=true"><script>globalThis.compromised=true</script>';
    render(<ExecutiveSummarySection summary={attack} />);
    expect(screen.getByText(attack)).toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector("img")).toBeNull();
    expect((globalThis as { compromised?: boolean }).compromised).toBeUndefined();
  });

  it("rejects external, query-bearing, fragment, and backslash report URLs", () => {
    expect(()=>resolveReportUrl("https://evil.test/reports/I/r.html")).toThrow(ApiClientError);
    expect(()=>resolveReportUrl("/reports/I/r.html?token=secret")).toThrow(ApiClientError);
    expect(()=>resolveReportUrl("/reports/I/r.html#content")).toThrow(ApiClientError);
    expect(()=>resolveReportUrl("/reports\\..\\secret.txt")).toThrow(ApiClientError);
    expect(resolveReportUrl("/reports/I/r.html")).toMatch(/^http:\/\/127\.0\.0\.1:8001\/reports\/I\/r\.html$/);
  });

  it("removes traversal and control characters from download filenames", () => {
    expect(safeFilename("../../secrets.txt")).toBe("secrets.txt");
    expect(filenameFromDisposition('attachment; filename="..\\..\\evil\r\n.txt"', "report.pdf")).toBe("evil__.txt");
  });

  it("redacts secret-like error details", () => {
    expect(sanitizeErrorMessage("connection_string=postgres://user:pass@host/db")).toBe("Request failed. Sensitive error details were hidden.");
    expect(sanitizeErrorMessage("Validation failed")).toBe("Validation failed");
  });

  it("does not fetch reports when stored session JSON is malformed", async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, "{bad-json"); const fetchMock=vi.fn(); vi.stubGlobal("fetch",fetchMock);
    await expect(fetchReportArtifact("/reports/I/r.pdf")).rejects.toMatchObject({ status:401 });
    expect(fetchMock).not.toHaveBeenCalled(); localStorage.clear(); vi.unstubAllGlobals();
  });
});
