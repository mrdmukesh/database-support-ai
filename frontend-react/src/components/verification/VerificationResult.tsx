import { formatSafeText } from "../../utils/investigation-formatters";
interface Props { actualResult?: unknown; confidenceImpact?: unknown; status?: unknown; notes?: unknown }
export function VerificationResult({ actualResult, confidenceImpact, status, notes }: Props) {
  return <section aria-label="Verification result">
    <dl>
      <dt>Status</dt><dd>{formatSafeText(status, "Pending")}</dd>
      <dt>Actual result</dt><dd>{formatSafeText(actualResult, "No result recorded.")}</dd>
      <dt>Confidence impact</dt><dd>{formatSafeText(confidenceImpact, "Not recorded")}</dd>
      <dt>Notes</dt><dd>{formatSafeText(notes, "No notes")}</dd>
    </dl>
  </section>;
}
