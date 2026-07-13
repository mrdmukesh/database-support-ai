import { useMemo, useState } from "react";
import type { FeedbackReviewRequest, InvestigationFeedback } from "../../models/feedback";
import type { InvestigationSummary } from "../../models/investigation";
import type { Workspace } from "../../models/workspace";

type Decision = "approve" | "reject";

interface Props {
  feedback: InvestigationFeedback;
  investigation?: InvestigationSummary;
  workspace?: Workspace;
  busy?: boolean;
  onReview: (feedbackId: string, payload: FeedbackReviewRequest) => Promise<void>;
}

const label = (value?: string | null) => value?.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()) || "Not recorded";
const tone = (value: string) => value.includes("APPROVED") || value === "HELPFUL" ? "success" : value.includes("REJECT") || value === "WRONG_ROOT_CAUSE" ? "danger" : "warning";
const section = (answer: string, heading: string) => answer.match(new RegExp(`## ${heading}\\s*([\\s\\S]*?)(?=\\n## |$)`, "i"))?.[1]?.trim() || "Not recorded";

function evidenceFrom(answer: string) {
  const ids = [...new Set(answer.match(/\b(?:SQL|PROC|META|DOC)-\d+\b/g) || [])];
  return ids.map((id) => ({
    id,
    type: id.startsWith("SQL") ? "SQL evidence" : id.startsWith("PROC") ? "Procedure evidence" : id.startsWith("META") ? "Metadata evidence" : "Knowledge context",
    source: id.startsWith("SQL") ? "Executed read-only query" : id.startsWith("PROC") ? "Procedure definition" : "Investigation package",
    summary: answer.split("\n").find((line) => line.includes(id))?.replace(/^[-*]\s*/, "") || "Referenced by the investigation result.",
  }));
}

export function FeedbackReviewWorkspace({ feedback, investigation, workspace, busy = false, onReview }: Props) {
  const [decision, setDecision] = useState<Decision | null>(null);
  const [notes, setNotes] = useState(feedback.review_notes || "");
  const [confidence, setConfidence] = useState(0.95);
  const [title, setTitle] = useState(`Verified resolution: ${feedback.actual_root_cause || investigation?.detected_intent || "database issue"}`);
  const [severity, setSeverity] = useState("medium");
  const [issueType, setIssueType] = useState(investigation?.detected_intent || "");
  const [reasonError, setReasonError] = useState("");
  const answer = investigation?.ai_answer || "";
  const evidence = useMemo(() => evidenceFrom(answer), [answer]);
  const rootCause = section(answer, "Root Cause Analysis");
  const recommendation = section(answer, "Recommendation");
  const missing = section(answer, "Missing Information / Clarifying Questions");

  async function confirm() {
    if (decision === "reject" && !notes.trim()) { setReasonError("A rejection reason is required."); return; }
    if (!decision) return;
    try {
      await onReview(feedback.id, { approved: decision === "approve", title: decision === "approve" ? title.trim() || null : null, review_notes: notes.trim(), issue_type: issueType.trim(), severity, rollback_plan: feedback.rollback_used || "", confidence_after_approval: confidence });
      setDecision(null); setReasonError("");
    } catch { /* The parent renders the API failure and keeps the dialog available for retry. */ }
  }

  return <article className="feedback-review" aria-labelledby={`feedback-${feedback.id}`}>
    <header className="feedback-review-header">
      <div><p className="eyebrow">Feedback Review</p><h3 id={`feedback-${feedback.id}`}>Investigation {feedback.investigation_id}</h3><div className="feedback-badges"><span className="ui-badge" data-tone={tone(feedback.status)}>{label(feedback.status)}</span><span className="ui-badge" data-tone={tone(feedback.rating)}>{label(feedback.rating)}</span></div></div>
      <dl><div><dt>Submitted by</dt><dd>Not exposed by API</dd></div><div><dt>Submitted</dt><dd>{feedback.created_at ? new Date(feedback.created_at).toLocaleString() : "Not recorded"}</dd></div><div><dt>Workspace</dt><dd>{workspace?.name || feedback.workspace_id}</dd></div><div><dt>Severity</dt><dd>{label(severity)}</dd></div><div><dt>Review state</dt><dd>{label(feedback.status)}</dd></div></dl>
    </header>

    <div className="feedback-sticky-actions" aria-label="Review actions"><button className="ui-button ui-button-primary" disabled={busy || feedback.status !== "PENDING_APPROVAL"} onClick={() => setDecision("approve")}>Approve as Knowledge</button><button className="ui-button ui-button-danger" disabled={busy || feedback.status !== "PENDING_APPROVAL"} onClick={() => setDecision("reject")}>Reject Feedback</button><button className="ui-button ui-button-secondary" disabled title="The current API has no request-more-information state.">Request More Information</button></div>

    <section className="ui-card feedback-summary" aria-labelledby={`summary-${feedback.id}`}><div className="ui-card-header"><h4 id={`summary-${feedback.id}`}>Executive summary</h4><p>Compare the generated conclusion with the submitted correction before making knowledge reusable.</p></div><div className="feedback-summary-grid"><div><span>Original user question</span><strong>{investigation?.user_question || "Not available"}</strong></div><div><span>AI-generated root cause</span><p>{rootCause}</p></div><div><span>AI confidence</span><strong>{investigation?.confidence_score == null ? "Not recorded" : `${Math.round(investigation.confidence_score * 100)}%`}</strong></div><div><span>Feedback rating</span><span className="ui-badge" data-tone={tone(feedback.rating)}>{label(feedback.rating)}</span></div><div className="correction"><span>User-provided actual root cause</span><strong>{feedback.actual_root_cause || "Not provided"}</strong></div><div><span>Production issue resolved</span><strong>{feedback.production_issue_resolved == null ? "Not recorded" : feedback.production_issue_resolved ? "Yes" : "No"}</strong></div></div></section>

    <div className="feedback-comparison">
      <section className="ui-card ai-panel"><div className="ui-card-header"><h4>AI Investigation Result</h4><p>Generated result; validate it against live evidence.</p></div><dl className="review-fields"><div><dt>Root-cause claim</dt><dd>{rootCause}</dd></div><div><dt>Confidence</dt><dd>{investigation?.confidence_score == null ? "Not recorded" : `${Math.round(investigation.confidence_score * 100)}%`}</dd></div><div><dt>Evidence IDs</dt><dd>{evidence.length ? evidence.map((item) => <a key={item.id} href={`#evidence-${item.id}`}>{item.id}</a>) : "None cited"}</dd></div><div><dt>Recommended fix</dt><dd>{recommendation}</dd></div><div><dt>Missing evidence</dt><dd>{missing}</dd></div><div><dt>Support status</dt><dd>{evidence.length ? "Evidence referenced" : "Evidence reference unavailable"}</dd></div></dl></section>
      <section className="ui-card correction-panel"><div className="ui-card-header"><h4>Reviewer Correction</h4><p>User-submitted operational outcome.</p></div><dl className="review-fields">{[["Actual root cause",feedback.actual_root_cause],["Actual fix applied",feedback.actual_fix_applied],["SQL or procedure changed",feedback.sql_or_procedure_changed],["Test cases executed",feedback.test_cases_executed],["Proof of fix",feedback.proof_of_fix],["Rollback used",feedback.rollback_used],["Notes",feedback.notes]].map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value||"Not provided"}</dd></div>)}</dl></section>
    </div>

    <section className="ui-card"><div className="ui-card-header"><h4>Evidence</h4><p>References extracted from the saved investigation answer. Details do not expose data beyond that answer.</p></div>{evidence.length ? <div className="ui-table-wrap"><table className="ui-table"><thead><tr><th>Evidence ID</th><th>Type</th><th>Source</th><th>Summary</th><th>Support status</th><th>View details</th></tr></thead><tbody>{evidence.map((item)=><tr id={`evidence-${item.id}`} key={item.id}><td><a href={`#evidence-${item.id}`}>{item.id}</a></td><td>{item.type}</td><td>{item.source}</td><td>{item.summary}</td><td><span className="ui-badge" data-tone="success">Referenced</span></td><td><details><summary>View details</summary><p>{item.summary}</p></details></td></tr>)}</tbody></table></div>:<div className="ui-empty"><strong>No structured evidence references found</strong><p>Open the original investigation to inspect its complete evidence package.</p></div>}</section>

    <section className="ui-card knowledge-preview"><div className="ui-card-header"><h4>Knowledge article preview</h4><p>Only fields accepted by the existing review API are editable.</p></div><div className="preview-grid"><label className="ui-form-field">Proposed title<input className="ui-control" value={title} onChange={(e)=>setTitle(e.target.value)} disabled={feedback.status!=="PENDING_APPROVAL"}/></label><label className="ui-form-field">Issue type<input className="ui-control" value={issueType} onChange={(e)=>setIssueType(e.target.value)} disabled={feedback.status!=="PENDING_APPROVAL"}/></label><label className="ui-form-field">Severity<select className="ui-control" value={severity} onChange={(e)=>setSeverity(e.target.value)} disabled={feedback.status!=="PENDING_APPROVAL"}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label><div><span>Confidence after approval</span><p>{Math.round(confidence*100)}%</p></div><div><span>Symptoms</span><p>{investigation?.user_question || "Not available"}</p></div><div><span>Verified root cause</span><p>{feedback.actual_root_cause || "Not provided"}</p></div><div><span>Verified fix</span><p>{feedback.actual_fix_applied || "Not provided"}</p></div><div><span>Test evidence</span><p>{feedback.proof_of_fix || feedback.test_cases_executed || "Not provided"}</p></div><div><span>Rollback plan</span><p>{feedback.rollback_used || "Not provided"}</p></div><div><span>Workspace visibility</span><p>{workspace?.name || feedback.workspace_id} only</p></div></div></section>

    <section className="ui-card decision-panel"><div className="ui-card-header"><h4>Review decision</h4><p>Approval creates reusable workspace knowledge; rejection retains the feedback for audit.</p></div><div className="decision-fields"><label className="ui-form-field">Review notes<textarea className="ui-control" value={notes} onChange={(e)=>{setNotes(e.target.value);setReasonError("");}}/></label><label className="ui-form-field">Approval confidence<input aria-label="Approval confidence" className="ui-control" type="number" min="0" max="1" step="0.05" value={confidence} onChange={(e)=>setConfidence(Number(e.target.value))}/></label></div></section>

    {decision ? <div className="review-dialog-backdrop"><div role="dialog" aria-modal="true" aria-labelledby="review-dialog-title" className="review-dialog"><h4 id="review-dialog-title">{decision === "approve" ? "Approve feedback as knowledge?" : "Reject feedback?"}</h4>{decision === "approve" ? <p>Approved feedback will become reusable workspace knowledge and may influence future investigations. Live database evidence remains authoritative.</p> : <><p>Rejected feedback will not become reusable knowledge.</p><label className="ui-form-field">Rejection reason <span aria-hidden="true">*</span><textarea autoFocus className="ui-control" value={notes} onChange={(e)=>{setNotes(e.target.value);setReasonError("");}}/></label>{reasonError?<p className="ui-alert" role="alert">{reasonError}</p>:null}</>}<div className="dialog-actions"><button className={decision==="approve"?"ui-button ui-button-primary":"ui-button ui-button-danger"} disabled={busy} onClick={()=>void confirm()}>{decision === "approve" ? "Confirm approval" : "Confirm rejection"}</button><button className="ui-button ui-button-secondary" onClick={()=>{setDecision(null);setReasonError("");}}>Cancel</button></div></div></div>:null}
  </article>;
}
