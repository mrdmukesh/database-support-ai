import { investigationText } from "./investigation-parser";

export const MISSING_EVIDENCE_LABEL = "Evidence unavailable";

/** Null-safe plain text for React text nodes; deliberately performs no HTML rendering. */
export function formatSafeText(value: unknown, fallback = ""): string {
  const text = investigationText(value).trim();
  return text || fallback;
}

/** Display the backend-provided confidence only; never derive a new confidence value. */
export function formatConfidenceLabel(confidence: number | null | undefined): string {
  return typeof confidence === "number" && Number.isFinite(confidence)
    ? `${Math.round(confidence * 100)}%`
    : "Confidence unavailable";
}

export function formatSourceCount(sourceCount: number | null | undefined): string {
  if (typeof sourceCount !== "number" || !Number.isFinite(sourceCount) || sourceCount < 0) {
    return "Sources unavailable";
  }
  return `${sourceCount} ${sourceCount === 1 ? "source" : "sources"}`;
}

export function formatHumanReviewLabel(requiresHumanReview: boolean | null | undefined): string {
  if (requiresHumanReview == null) return "Review status unavailable";
  return requiresHumanReview ? "Human review required" : "No safety findings";
}

export function formatMissingEvidenceState(
  evidence: readonly unknown[] | null | undefined,
): string | null {
  return evidence?.length ? null : MISSING_EVIDENCE_LABEL;
}
