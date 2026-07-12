import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { loadSavedInvestigation } from "../../api/investigation-api";
import { EvidenceSection } from "../../components/investigation/EvidenceSection";
import { ExecutiveSummarySection } from "../../components/investigation/ExecutiveSummarySection";
import { InvestigationBadges } from "../../components/investigation/InvestigationBadges";
import { InvestigationHeader } from "../../components/investigation/InvestigationHeader";
import { RecommendationSection } from "../../components/investigation/RecommendationSection";
import { RootCauseSection } from "../../components/investigation/RootCauseSection";
import type { SavedInvestigation } from "../../models/investigation";
import { parseLegacyAssistantMessage } from "../../utils/investigation-parser";

type LoadState =
  | { status: "loading" }
  | { status: "not-found" }
  | { status: "error"; message: string }
  | { status: "loaded"; investigation: SavedInvestigation };

export function InvestigationResultPage() {
  const { investigationId } = useParams<{ investigationId: string }>();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    const id = investigationId?.trim();
    if (!id) {
      setState({ status: "not-found" });
      return;
    }

    const controller = new AbortController();
    setState({ status: "loading" });
    async function load() {
      try {
        const investigation = await loadSavedInvestigation(id, controller.signal);
        setState({ status: "loaded", investigation });
      } catch (cause: unknown) {
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
    return () => controller.abort();
  }, [investigationId]);

  if (state.status === "loading") {
    return <p role="status">Loading investigation...</p>;
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
  return (
    <article className="management-page" aria-labelledby="investigation-result-title">
      <InvestigationHeader investigationId={result.id || investigationId} question={result.user_question}
        intent={result.detected_intent} status={result.status} createdAt={result.created_at} />
      <InvestigationBadges confidence={result.confidence_score} />
      <ExecutiveSummarySection summary={parsed.raw} />
      <RootCauseSection rootCauses={parsed.rootCauses} />
      <EvidenceSection evidence={parsed.confirmedFacts} />
      <RecommendationSection recommendations={parsed.recommendations} />
    </article>
  );
}
