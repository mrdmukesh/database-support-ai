import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { loadSavedInvestigation } from "../../api/investigation-api";
import { ExecutiveSummarySection } from "../../components/investigation/ExecutiveSummarySection";
import { RecommendationSection } from "../../components/investigation/RecommendationSection";
import { RootCauseSection } from "../../components/investigation/RootCauseSection";
import { ReportDownloads } from "../../components/reports/ReportDownloads";
import { VerificationPanel } from "../../components/verification/VerificationPanel";
import { useAuth } from "../../hooks/use-auth";
import type { SavedInvestigation } from "../../models/investigation";
import { extractSection, extractSectionBullets, parseLegacyAssistantMessage } from "../../utils/investigation-parser";
import { Alert, Card, ConfidenceBadge, EvidenceTable, PageHeader, RiskBadge, SkeletonLoader, SqlCodeBlock, StatusBadge, humanize } from "../../components/ui";

type LoadState =
  | { status: "loading" }
  | { status: "not-found" }
  | { status: "error"; message: string }
  | { status: "loaded"; investigation: SavedInvestigation };

export function InvestigationResultPage() {
  const { user } = useAuth();
  const { investigationId } = useParams<{ investigationId: string }>();
  const normalizedInvestigationId = investigationId?.trim() ?? "";
  const [state, setState] = useState<LoadState>(() => (
    normalizedInvestigationId ? { status: "loading" } : { status: "not-found" }
  ));
  const requestIdRef = useRef(0);

  useEffect(() => {
    const id = normalizedInvestigationId;
    if (!id) {
      requestIdRef.current += 1;
      setState({ status: "not-found" });
      return;
    }

    const requestedId = id;
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;

    const controller = new AbortController();
    setState({ status: "loading" });
    async function load() {
      try {
        const investigation = await loadSavedInvestigation(requestedId, controller.signal);
        if (requestIdRef.current !== requestId) return;
        setState({ status: "loaded", investigation });
      } catch (cause: unknown) {
        if (controller.signal.aborted) return;
        if (requestIdRef.current !== requestId) return;
        const error = cause as { name?: unknown; status?: unknown; message?: unknown } | null;
        if (error?.name === "AbortError") return;
        if (error?.status === 404) {
          setState({ status: "not-found" });
          return;
        }
        setState({
          status: "error",
          message: typeof error?.message === "string"
            ? error.message
            : "Investigation could not be loaded.",
        });
      }
    }
    void load();
    return () => {
      controller.abort();
    };
  }, [normalizedInvestigationId]);

  if (state.status === "loading") {
    return <div className="management-page"><SkeletonLoader label="Loading investigation" lines={8} /></div>;
  }

  if (state.status === "not-found") {
    return (
      <section className="startup-card" aria-labelledby="investigation-not-found-title">
        <h2 id="investigation-not-found-title">Investigation not found</h2>
        <p>The requested investigation is unavailable.</p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="startup-card" aria-labelledby="investigation-error-title">
        <h2 id="investigation-error-title">Unable to load investigation</h2>
        <div role="alert">{state.message}</div>
      </section>
    );
  }

  const result = state.investigation;
  const parsed = parseLegacyAssistantMessage(result.ai_answer);
  const affectedObjects = extractSectionBullets(result.ai_answer, "Relevant Objects Investigated", 8);
  const sql = extractSection(result.ai_answer, "Recommended Next SQL");
  const limitations = extractSectionBullets(result.ai_answer, "Missing Information / Clarifying Questions", 8);
  const risk = extractSectionBullets(result.ai_answer, "Recommendation", 8).find((item) => item.toLowerCase().startsWith("risk:"))?.slice(5).trim();
  const evidenceRows = parsed.confirmedFacts.map((finding, index) => {
    const id = finding.match(/\b(?:SQL|DOC|EVIDENCE)-?\d+\b/i)?.[0] || `E-${index + 1}`;
    const source = affectedObjects[index]?.split(":")[1]?.trim() || affectedObjects[index]?.split(" ")[0] || "Investigation evidence";
    return { id, source, finding, state: "confirmed", contribution: "Supporting" };
  });
  return (
    <article className="management-page" aria-labelledby="investigation-result-title">
      <PageHeader eyebrow="Investigation result" title={`Investigation ${result.id || normalizedInvestigationId}`} description={result.user_question} />
      <Card className="investigation-overview">
        <div className="investigation-overview-badges"><StatusBadge status={result.status} /><ConfidenceBadge confidence={result.confidence_score} /><RiskBadge risk={risk} /><StatusBadge status="Verification available" /></div>
        <dl><dt>Workspace</dt><dd>{result.workspace_id}</dd><dt>Selected database</dt><dd><strong>{result.connection_name || "Unavailable"}</strong><small>{result.connection_id}</small></dd><dt>Investigation type</dt><dd>{humanize(result.detected_intent)}</dd><dt>Created</dt><dd>{new Date(result.created_at).toLocaleString()}</dd></dl>
      </Card>
      <div className="investigation-result-grid">
        <RootCauseSection rootCauses={parsed.rootCauses} />
        <ExecutiveSummarySection summary={extractSection(parsed.raw, "Stage 6 - Reason") || "No executive summary was returned."} />
        <Card className="result-card-wide" title="Supporting evidence"><EvidenceTable rows={evidenceRows} /></Card>
        <Card title="Affected database objects">{affectedObjects.length ? <ul className="object-list">{affectedObjects.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No affected objects were confirmed.</p>}</Card>
        <RecommendationSection recommendations={parsed.recommendations} />
        <Card className="result-card-wide" title="Evidence SQL" description="Read-only statements used or recommended during evidence collection."><SqlCodeBlock sql={sql} /></Card>
        <Card title="Limitations">{limitations.length ? <ul>{limitations.map((item) => <li key={item}>{item}</li>)}</ul> : <Alert tone="success">No limitations were recorded.</Alert>}</Card>
        <Card title="Reports"><ReportDownloads reports={result.report} showAiTrace={user?.role === "super_admin" || user?.role === "organization_admin"} /></Card>
      </div>
      <Card className="result-card-wide" title="Verification checks" description="Run read-only checks to validate key claims and update confidence."><VerificationPanel investigationId={result.id} /></Card>
      <details className="technical-details"><summary>Technical details</summary><dl><dt>Investigation ID</dt><dd>{result.id}</dd><dt>Raw status</dt><dd>{result.status}</dd><dt>Raw intent</dt><dd>{result.detected_intent}</dd><dt>Connection ID</dt><dd>{result.connection_id}</dd></dl><pre>{parsed.raw}</pre></details>
    </article>
  );
}
