import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReportDownloads } from "./ReportDownloads";
const fetchReportArtifact = vi.fn();
vi.mock("../../api/report-api", () => ({ fetchReportArtifact: (...args: unknown[]) => fetchReportArtifact(...args) }));
describe("ReportDownloads", () => {
  beforeEach(() => { fetchReportArtifact.mockReset(); vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:safe"), revokeObjectURL: vi.fn() }); });
  it("shows complete available reports and optional trace", () => { render(<ReportDownloads showAiTrace reports={{ html: "/reports/x/a.html", pdf: "/reports/x/a.pdf", docx: "/reports/x/a.docx", xlsx: "/reports/x/a.xlsx", audit_html: "/reports/x/b.html", audit_pdf: "/reports/x/b.pdf", audit_docx: "/reports/x/b.docx", audit_xlsx: "/reports/x/b.xlsx", ai_trace: "/reports/x/ai-debug-trace" }} />); expect(screen.getAllByRole("button")).toHaveLength(9); });
  it("shows only partial links and hides trace unless authorized for visibility", () => { render(<ReportDownloads reports={{ pdf: "/reports/x/a.pdf", ai_trace: "/reports/x/ai-debug-trace" }} />); expect(screen.getByRole("button", { name: "Download PDF" })).toBeInTheDocument(); expect(screen.queryByText("Download AI Trace")).not.toBeInTheDocument(); });
  it("renders nothing for empty reports", () => { const { container } = render(<ReportDownloads reports={{}} />); expect(container).toBeEmptyDOMElement(); });
  it("handles unauthorized and failed downloads", async () => { fetchReportArtifact.mockRejectedValue(new Error("Authentication is required.")); render(<ReportDownloads reports={{ pdf: "/reports/x/a.pdf" }} />); fireEvent.click(screen.getByRole("button")); expect(await screen.findByRole("alert")).toHaveTextContent("Authentication is required."); });
  it("handles popup blocking safely", async () => { fetchReportArtifact.mockResolvedValue({ blob: new Blob(["x"]), filename: "a.html", contentType: "text/html" }); vi.spyOn(window, "open").mockReturnValue(null); render(<ReportDownloads reports={{ html: "/reports/x/a.html" }} />); fireEvent.click(screen.getByRole("button")); await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Popup blocked")); });
});
