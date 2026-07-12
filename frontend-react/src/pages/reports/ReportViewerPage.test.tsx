import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReportViewerPage } from "./ReportViewerPage";
const fetchReportArtifact = vi.fn();
vi.mock("../../api/report-api", () => ({ fetchReportArtifact: (...args: unknown[]) => fetchReportArtifact(...args) }));
describe("ReportViewerPage security", () => {
  beforeEach(() => { fetchReportArtifact.mockReset(); vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:authenticated-report"), revokeObjectURL: vi.fn() }); });
  it("rejects external and non-HTML paths without fetching", async () => { render(<MemoryRouter initialEntries={["/app/reports/view?path=https://evil.test/x.html"]}><ReportViewerPage /></MemoryRouter>); expect(await screen.findByRole("alert")).toBeInTheDocument(); expect(fetchReportArtifact).not.toHaveBeenCalled(); });
  it("renders authenticated HTML only in a script-disabled sandboxed blob iframe", async () => { fetchReportArtifact.mockResolvedValue({ blob: new Blob(["<script>bad()</script>"]), filename: "r.html", contentType: "text/html" }); render(<MemoryRouter initialEntries={["/app/reports/view?path=/reports/INV/r.html"]}><ReportViewerPage /></MemoryRouter>); const frame = await screen.findByTitle("Investigation HTML report"); expect(frame).toHaveAttribute("src", "blob:authenticated-report"); expect(frame).toHaveAttribute("sandbox", ""); expect(document.querySelector("script")).toBeNull(); });
});
