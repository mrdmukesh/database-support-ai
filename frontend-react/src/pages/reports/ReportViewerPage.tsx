import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchReportArtifact } from "../../api/report-api";

export function ReportViewerPage() {
  const [params] = useSearchParams();
  const path = params.get("path");
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | null = null;
    if (!path || !path.startsWith("/reports/") || !path.toLowerCase().endsWith(".html")) {
      setError("A valid HTML report link is required.");
      return () => controller.abort();
    }
    setError(null);
    void fetchReportArtifact(path, controller.signal).then((artifact) => {
      objectUrl = URL.createObjectURL(artifact.blob);
      setUrl(objectUrl);
    }).catch((cause: unknown) => {
      if ((cause as { name?: string })?.name !== "AbortError") setError(cause instanceof Error ? cause.message : "Report could not be loaded.");
    });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [path]);
  if (error) return <div role="alert">{error}</div>;
  if (!url) return <p role="status">Loading report...</p>;
  return <iframe title="Investigation HTML report" src={url} sandbox="" referrerPolicy="no-referrer" />;
}
