import { useState } from "react";
import type { ReportLinks } from "../../models/report";
import { fetchReportArtifact, type ReportLinkKey } from "../../api/report-api";

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
  if (!entries.length) return null;

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

  return <section aria-label="Report downloads">
    <div>{entries.map((key) => <button type="button" key={key} onClick={() => void activate(key)}>{labels[key]}</button>)}</div>
    {error ? <div role="alert">{error}</div> : null}
  </section>;
}
