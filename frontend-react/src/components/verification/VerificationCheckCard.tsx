import type { VerificationCheck } from "../../models/verification";
import { VerificationResult } from "./VerificationResult";
interface Props { check: VerificationCheck; busy?: boolean; onRun: (id: string) => void; onSkip: (id: string) => void }
export function VerificationCheckCard({ check, busy = false, onRun, onSkip }: Props) {
  const pending = check.status === "Pending";
  return <article aria-labelledby={`verification-${check.id}`}>
    <h4 id={`verification-${check.id}`}>{check.claim}</h4>
    {check.purpose ? <p><strong>Purpose:</strong> {check.purpose}</p> : null}
    {check.claim_being_verified ? <p><strong>Claim being verified:</strong> {check.claim_being_verified}</p> : null}
    {check.verification_sql ? <div><strong>Verification SQL</strong><pre>{check.verification_sql}</pre></div> : null}
    <p><strong>Expected:</strong> {check.expected_result || "Not provided"}</p>
    <VerificationResult actualResult={check.actual_result_summary} confidenceImpact={check.confidence_impact} status={check.status} notes={check.notes} />
    {pending ? <div><button type="button" disabled={busy} onClick={() => onRun(check.id)}>Run this check</button><button type="button" disabled={busy} onClick={() => onSkip(check.id)}>Skip</button></div>
      : <p>This check is {check.status}.</p>}
  </article>;
}
