import { useState } from "react";
import type { ReportLinks } from "../../models/report";
import { fetchReportArtifact, type ReportLinkKey } from "../../api/report-api";
import { Alert, SecondaryButton } from "../ui";

interface Props { reports: ReportLinks | null | undefined; showAiTrace?: boolean }
const labels: Record<ReportLinkKey, string> = {
  html: "View HTML Report", pdf: "Download PDF", docx: "Download Word", xlsx: "Download Excel",
  audit_html: "View Audit HTML", audit_pdf: "Download Audit PDF", audit_docx: "Download Audit Word",
  audit_xlsx: "Download Audit Excel", ai_trace: "Download AI Trace",
};

export function ReportDownloads({ reports, showAiTrace = false }: Props) {
  const [error, setError] = useState<string | null>(null);
  const entries = (Object.keys(labels) as ReportLinkKey[]).filter((key) => {
    if (key === "ai_trace" && !showAiTrace) return false;
    return Boolean(reports?.[key]);
  });
  const primaryFormats: ReportLinkKey[] = ["html", "pdf", "docx", "xlsx"];

  async function activate(key: ReportLinkKey) {
    const path = reports?.[key];
    if (!path) return;
    setError(null);
    let objectUrl: string | null = null;
    try {
      const artifact = await fetchReportArtifact(path);
      objectUrl = URL.createObjectURL(artifact.blob);
      if (key === "html" || key === "audit_html") {
        const popup = window.open(objectUrl, "_blank", "noopener,noreferrer");
        if (!popup) throw new Error("Popup blocked. Allow popups to view HTML report.");
      } else {
        const link = document.createElement("a");
        link.href = objectUrl;
        link.download = artifact.filename;
        link.click();
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Report download failed.");
    } finally {
      if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl!), 0);
    }
  }

  return <section className="report-actions" aria-label="Report downloads">
    <div className="report-action-grid">{primaryFormats.map((key) => <SecondaryButton key={key} disabled={!reports?.[key]} onClick={() => void activate(key)}>{labels[key]}</SecondaryButton>)}</div>
    {entries.filter((key) => !primaryFormats.includes(key)).length ? <details><summary>Audit and diagnostic reports</summary><div className="report-action-grid">{entries.filter((key) => !primaryFormats.includes(key)).map((key) => <SecondaryButton key={key} onClick={() => void activate(key)}>{labels[key]}</SecondaryButton>)}</div></details> : null}
    {!entries.length ? <Alert tone="info" title="Reports unavailable">Report generation did not return any downloadable files.</Alert> : null}
    {error ? <Alert title="Report unavailable">{error === "Report file not found" ? "The report is no longer available. Regenerate the investigation report or contact an administrator." : error}</Alert> : null}
  </section>;
}

export const ReportActions = ReportDownloads;
