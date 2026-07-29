import { useCallback, useEffect, useState } from "react";

import {
  cancelAgenticInvestigation,
  loadInvestigationProgress,
} from "../../api/investigation-api";
import type {
  InvestigationProgress,
  InvestigationProgressStep,
} from "../../models/investigation";
import { humanize } from "../ui";

interface Props {
  investigationId: string;
}

type ProgressState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "loaded"; progress: InvestigationProgress };

const budgetItems = [
  ["iterations", "Iterations"],
  ["sql_queries", "Queries"],
  ["total_rows", "Rows"],
  ["execution_seconds", "Duration"],
  ["llm_calls", "LLM calls"],
] as const;

function EvidenceList({ step }: { step: InvestigationProgressStep }) {
  if (!step.created_evidence.length) return <p className="progress-muted">No new evidence created.</p>;
  return (
    <ul className="progress-evidence-list">
      {step.created_evidence.map((item, index) => (
        <li key={`${item.evidence_id}-${index}`}>
          <strong>{item.evidence_id || "Evidence"}</strong>
          <span>{item.purpose || item.supports_claim || "Verified evidence result"}</span>
          <small>{humanize(item.evidence_semantics)} · {item.row_count} rows</small>
        </li>
      ))}
    </ul>
  );
}

function TimelineStep({ step }: { step: InvestigationProgressStep }) {
  const [expanded, setExpanded] = useState(false);
  const panelId = `progress-step-${step.iteration}-${step.created_at.replace(/\W/g, "")}`;
  return (
    <li className="progress-timeline-step" data-result={step.result.toLowerCase()}>
      <span className="progress-timeline-marker" aria-hidden="true" />
      <article>
        <header>
          <div>
            <span className="progress-kicker">Iteration {step.iteration}</span>
            <h4>{humanize(step.action)}</h4>
          </div>
          <span className="progress-result-badge">{humanize(step.result)}</span>
        </header>
        <p>{step.reason || "No selection reason recorded."}</p>
        <button
          className="progress-disclosure"
          type="button"
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Hide evidence" : `Show evidence (${step.created_evidence.length})`}
        </button>
        {expanded ? <div id={panelId}><EvidenceList step={step} /></div> : null}
      </article>
    </li>
  );
}

export function InvestigationProgressPanel({ investigationId }: Props) {
  const [state, setState] = useState<ProgressState>({ status: "loading" });
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState("");

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const progress = await loadInvestigationProgress(investigationId, signal);
      setState({ status: "loaded", progress });
    } catch (cause) {
      if (signal?.aborted) return;
      setState({
        status: "error",
        message: cause instanceof Error ? cause.message : "Progress could not be loaded.",
      });
    }
  }, [investigationId]);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (state.status !== "loaded" || state.progress.terminal) return;
    const timer = window.setTimeout(() => void load(), 5000);
    return () => window.clearTimeout(timer);
  }, [load, state]);

  if (state.status === "loading") {
    return (
      <section className="agentic-progress-shell" aria-label="Investigation progress">
        <div className="agentic-progress-loading" role="status">
          <span className="progress-spinner" aria-hidden="true" />
          Loading investigation progress…
        </div>
      </section>
    );
  }
  if (state.status === "error") {
    return (
      <section className="agentic-progress-shell" aria-labelledby="progress-error-title">
        <h2 id="progress-error-title">Investigation progress unavailable</h2>
        <p role="alert">{state.message}</p>
        <button className="ui-button ui-button-secondary" type="button" onClick={() => void load()}>
          Retry
        </button>
      </section>
    );
  }

  const progress = state.progress;
  const questionTotal = Object.values(progress.question_counts).reduce((sum, value) => sum + value, 0);
  const cancel = async () => {
    setCancelling(true);
    setCancelError("");
    try {
      await cancelAgenticInvestigation(investigationId);
      await load();
    } catch (cause) {
      setCancelError(cause instanceof Error ? cause.message : "Cancellation failed.");
    } finally {
      setCancelling(false);
    }
  };

  if (!progress.agentic) {
    return (
      <section className="agentic-progress-shell progress-legacy" aria-labelledby="progress-legacy-title">
        <div>
          <span className="progress-kicker">Deterministic fallback</span>
          <h2 id="progress-legacy-title">Progress timeline not recorded</h2>
          <p>This investigation predates agentic progress tracking. The existing report remains available below.</p>
        </div>
        <span className="evidence-source-badge">Deterministic Fallback</span>
      </section>
    );
  }

  return (
    <section className="agentic-progress-shell" aria-labelledby="agentic-progress-title">
      <header className="agentic-progress-header">
        <div>
          <span className="progress-kicker">Agentic investigation</span>
          <h2 id="agentic-progress-title">Investigation progress</h2>
          <p>Iteration {progress.iteration_number} · {humanize(progress.current_state)}</p>
        </div>
        <div className="agentic-progress-actions">
          {progress.source_badges.map((badge) => <span className="evidence-source-badge" key={badge}>{badge}</span>)}
          {progress.can_cancel ? (
            <button className="ui-button progress-cancel" type="button" disabled={cancelling} onClick={() => void cancel()}>
              {cancelling ? "Cancelling…" : "Cancel investigation"}
            </button>
          ) : null}
        </div>
      </header>
      {cancelError ? <p className="progress-inline-error" role="alert">{cancelError}</p> : null}

      <div className="progress-summary-grid">
        <article className="progress-state-card">
          <span>Current state</span>
          <strong>{humanize(progress.current_state)}</strong>
          <small>{progress.terminal ? "Terminal" : "Investigation active"}</small>
        </article>
        <article className="progress-state-card">
          <span>Root cause</span>
          <strong>{humanize(progress.root_cause_status)}</strong>
          <small>Rejected AI text is excluded</small>
        </article>
        <article className="progress-state-card">
          <span>Fix readiness</span>
          <strong>{humanize(progress.fix_readiness_state)}</strong>
          <small>Deterministic prerequisites apply</small>
        </article>
      </div>

      <section className="progress-section" aria-labelledby="budget-title">
        <div className="progress-section-heading">
          <div><span className="progress-kicker">Guardrails</span><h3 id="budget-title">Budget usage</h3></div>
        </div>
        <dl className="progress-budget-grid">
          {budgetItems.map(([key, label]) => (
            <div key={key}><dt>{label}</dt><dd>{progress.budget[key] ?? 0}{key === "execution_seconds" ? "s" : ""}</dd></div>
          ))}
        </dl>
      </section>

      <div className="progress-two-column">
        <section className="progress-section" aria-labelledby="entity-title">
          <div className="progress-section-heading"><div><span className="progress-kicker">Scope</span><h3 id="entity-title">Resolved entities</h3></div></div>
          {progress.resolved_entities.length ? (
            <ul className="progress-entity-list">{progress.resolved_entities.map((entity, index) => (
              <li key={`${entity.entity_type}-${entity.value}-${index}`}>
                <span>{humanize(entity.entity_type)}</span><strong>{entity.value || "Value unavailable"}</strong><small>{humanize(entity.status)}</small>
              </li>
            ))}</ul>
          ) : <p className="progress-empty">No exact affected entity was recorded.</p>}
        </section>
        <section className="progress-section" aria-labelledby="question-title">
          <div className="progress-section-heading"><div><span className="progress-kicker">Evidence gaps</span><h3 id="question-title">Questions</h3></div><strong>{questionTotal}</strong></div>
          <dl className="progress-question-counts">
            {Object.entries(progress.question_counts).map(([label, count]) => <div key={label}><dt>{humanize(label)}</dt><dd>{count}</dd></div>)}
          </dl>
          {!questionTotal ? <p className="progress-empty">No structured evidence questions were recorded.</p> : null}
        </section>
      </div>

      {progress.failed_actions.length || progress.verified_absence.length ? (
        <section className="progress-distinction" aria-label="Failed actions and verified absence">
          <div><strong>Failed or blocked actions</strong><span>{progress.failed_actions.length}</span><p>Execution failure is not absence evidence.</p></div>
          <div><strong>Verified absence</strong><span>{progress.verified_absence.length}</span><p>Successful zero-row checks for a defined scope.</p></div>
        </section>
      ) : null}

      <section className="progress-section" aria-labelledby="timeline-title">
        <div className="progress-section-heading"><div><span className="progress-kicker">Evidence journey</span><h3 id="timeline-title">Completed steps</h3></div><strong>{progress.completed_steps.length}</strong></div>
        {progress.completed_steps.length ? (
          <ol className="progress-timeline">{progress.completed_steps.map((step) => <TimelineStep key={`${step.iteration}-${step.created_at}`} step={step} />)}</ol>
        ) : <p className="progress-empty">No agentic investigation step has completed yet.</p>}
      </section>

      {progress.terminal ? (
        <section className="progress-stop-card" aria-labelledby="stop-reason-title">
          <span className="progress-kicker">Investigation stopped</span>
          <h3 id="stop-reason-title">{humanize(progress.current_state)}</h3>
          <p>{progress.stop_reason || "No terminal reason was recorded."}</p>
        </section>
      ) : null}
    </section>
  );
}
