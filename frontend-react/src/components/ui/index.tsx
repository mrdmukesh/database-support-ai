import type { ButtonHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return <header className="ui-page-header"><div>{eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}<h2>{title}</h2>{description ? <p>{description}</p> : null}</div>{actions ? <div>{actions}</div> : null}</header>;
}
export function Card({ children, className = "", title, description }: { children: ReactNode; className?: string; title?: string; description?: string }) {
  return <section className={`ui-card ${className}`.trim()}>{title ? <header className="ui-card-header"><h3>{title}</h3>{description ? <p>{description}</p> : null}</header> : null}{children}</section>;
}
export function FormField({ label, htmlFor, hint, required, children }: { label: string; htmlFor: string; hint?: string; required?: boolean; children: ReactNode }) {
  return <div className="ui-form-field"><label htmlFor={htmlFor}>{label}{required ? <span aria-hidden="true"> *</span> : null}</label>{children}{hint ? <small id={`${htmlFor}-hint`}>{hint}</small> : null}</div>;
}
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) { return <select className="ui-control" {...props} />; }
export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea className="ui-control ui-textarea" {...props} />; }
export function PrimaryButton(props: ButtonHTMLAttributes<HTMLButtonElement>) { return <button className="ui-button ui-button-primary" type="button" {...props} />; }
export function SecondaryButton(props: ButtonHTMLAttributes<HTMLButtonElement>) { return <button className="ui-button ui-button-secondary" type="button" {...props} />; }

export function humanize(value: unknown, fallback = "Unavailable") {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) return fallback;
  return text.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}
export function StatusBadge({ status }: { status: unknown }) { return <span className="ui-badge" data-tone="status">{humanize(status)}</span>; }
export function ConfidenceBadge({ confidence }: { confidence: number | null | undefined }) {
  const value = Math.max(0, Math.min(1, Number(confidence ?? 0)));
  const tone = value >= .75 ? "success" : value >= .45 ? "warning" : "danger";
  return <span className="ui-badge" data-tone={tone}>Confidence {Math.round(value * 100)}%</span>;
}
export function RiskBadge({ risk }: { risk: unknown }) {
  const label = humanize(risk, "Risk not assessed"); const lower = label.toLowerCase();
  return <span className="ui-badge" data-tone={lower.includes("high") ? "danger" : lower.includes("medium") ? "warning" : "neutral"}>{label}</span>;
}
export function Alert({ children, tone = "error", title }: { children: ReactNode; tone?: "error" | "info" | "success" | "warning"; title?: string }) {
  return <div className="ui-alert" data-tone={tone} role={tone === "error" ? "alert" : "status"}>{title ? <strong>{title}</strong> : null}<div>{children}</div></div>;
}
export function SkeletonLoader({ lines = 4, label = "Loading" }: { lines?: number; label?: string }) {
  return <div className="ui-skeleton" role="status" aria-label={label}><span className="visually-hidden">{label}...</span>{Array.from({ length: lines }, (_, index) => <span key={index} />)}</div>;
}
export type ProgressState = "completed" | "active" | "pending" | "failed";
export function InvestigationProgress({ stages }: { stages: { label: string; state: ProgressState }[] }) {
  return <ol className="ui-progress" aria-label="Investigation progress">{stages.map((stage, index) => <li key={stage.label} data-state={stage.state}><span aria-hidden="true">{stage.state === "completed" ? "✓" : stage.state === "failed" ? "!" : index + 1}</span><div><strong>{stage.label}</strong><small>{humanize(stage.state)}</small></div></li>)}</ol>;
}
export interface EvidenceRow { id: string; source: string; finding: string; state?: string; contribution?: string; details?: string }
export function EvidenceTable({ rows }: { rows: EvidenceRow[] }) {
  if (!rows.length) return <EmptyState title="No confirmed evidence" message="No structured evidence was returned for this investigation." />;
  return <div className="ui-table-wrap"><table className="ui-table"><thead><tr><th>Evidence ID</th><th>Source object</th><th>Finding</th><th>Verification</th><th>Confidence impact</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td><code>{row.id}</code></td><td>{row.source}</td><td>{row.details ? <details><summary>{row.finding}</summary><p>{row.details}</p></details> : row.finding}</td><td><StatusBadge status={row.state || "confirmed"} /></td><td>{row.contribution || "Supporting"}</td></tr>)}</tbody></table></div>;
}
export function SqlCodeBlock({ sql, label = "Read-only SQL" }: { sql: string; label?: string }) { return <div className="ui-sql"><div><span>{label}</span><span>Read only</span></div><pre><code>{sql || "No SQL was recorded."}</code></pre></div>; }
export function EmptyState({ title = "Nothing to show", message }: { title?: string; message: string }) { return <div className="ui-empty"><strong>{title}</strong><p>{message}</p></div>; }
