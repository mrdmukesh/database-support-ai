import {
  formatConfidenceLabel,
  formatHumanReviewLabel,
  formatSourceCount,
} from "../../utils/investigation-formatters";

interface InvestigationBadgesProps {
  confidence: number | null | undefined;
  sourceCount?: number | null;
  requiresHumanReview?: boolean | null;
  findings?: readonly string[] | null;
}

export function InvestigationBadges({
  confidence,
  sourceCount,
  requiresHumanReview,
  findings,
}: InvestigationBadgesProps) {
  return (
    <div className="investigation-badges" aria-label="Investigation indicators">
      <span>Confidence {formatConfidenceLabel(confidence)}</span>
      <span>{formatSourceCount(sourceCount)}</span>
      <span>{formatHumanReviewLabel(requiresHumanReview)}</span>
      {(findings ?? []).map((finding, index) => (
        <span key={`${finding}-${index}`}>{formatSafeFinding(finding)}</span>
      ))}
    </div>
  );
}

function formatSafeFinding(finding: unknown): string {
  return typeof finding === "string" && finding.trim()
    ? finding.trim().replace(/_/g, " ")
    : "Finding unavailable";
}
