import type { VerificationCheck } from "../../models/verification";
import { VerificationResult } from "./VerificationResult";
import { SecondaryButton, SqlCodeBlock, StatusBadge } from "../ui";
interface Props { check: VerificationCheck; busy?: boolean; onRun: (id: string) => void; onSkip: (id: string) => void }
export function VerificationCheckCard({ check, busy = false, onRun, onSkip }: Props) {
  const pending = check.status.toLowerCase() === "pending";
  const visualStatus = busy && pending ? "Running" : check.status;
  return <article className="verification-check" data-status={visualStatus.toLowerCase()} aria-labelledby={`verification-${check.id}`}>
    <header><div><span>Verification check</span><h4 id={`verification-${check.id}`}>{check.claim_being_verified || check.claim}</h4></div><StatusBadge status={visualStatus} /></header>
    {check.claim && check.claim !== check.claim_being_verified ? <p>{check.claim}</p> : null}
    <div className="verification-meta"><p><strong>Purpose</strong><span>{check.purpose || "Not provided"}</span></p><p><strong>Expected result</strong><span>{check.expected_result || "Not provided"}</span></p></div>
    {check.verification_sql ? <SqlCodeBlock sql={check.verification_sql} label="Verification SQL" /> : null}
    <VerificationResult actualResult={check.actual_result_summary} confidenceImpact={check.confidence_impact} status={check.status} notes={check.notes} />
    {pending ? <div className="verification-actions"><SecondaryButton disabled={busy} aria-busy={busy} onClick={() => onRun(check.id)}>{busy ? "Running…" : "Run check"}</SecondaryButton><SecondaryButton disabled={busy} onClick={() => onSkip(check.id)}>Skip</SecondaryButton></div>
      : null}
  </article>;
}
