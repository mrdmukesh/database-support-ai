import { describe, expect, it } from "vitest";
import {
  MISSING_EVIDENCE_LABEL,
  formatConfidenceLabel,
  formatHumanReviewLabel,
  formatMissingEvidenceState,
  formatSafeText,
  formatSourceCount,
} from "./investigation-formatters";

describe("investigation formatters", () => {
  it("formats safe plain text without interpreting markup", () => {
    expect(formatSafeText(" <script>alert(1)</script> ")).toBe("<script>alert(1)</script>");
    expect(formatSafeText(null, "Missing")).toBe("Missing");
    expect(formatSafeText("", "Missing")).toBe("Missing");
    expect(formatSafeText(0)).toBe("0");
  });

  it("labels backend confidence including zero without recalculating missing values", () => {
    expect(formatConfidenceLabel(0.876)).toBe("88%");
    expect(formatConfidenceLabel(0)).toBe("0%");
    expect(formatConfidenceLabel(null)).toBe("Confidence unavailable");
    expect(formatConfidenceLabel(Number.NaN)).toBe("Confidence unavailable");
  });

  it("formats singular, plural, zero, missing, and malformed source counts", () => {
    expect(formatSourceCount(0)).toBe("0 sources");
    expect(formatSourceCount(1)).toBe("1 source");
    expect(formatSourceCount(2)).toBe("2 sources");
    expect(formatSourceCount(null)).toBe("Sources unavailable");
    expect(formatSourceCount(-1)).toBe("Sources unavailable");
  });

  it("formats every human-review state", () => {
    expect(formatHumanReviewLabel(true)).toBe("Human review required");
    expect(formatHumanReviewLabel(false)).toBe("No safety findings");
    expect(formatHumanReviewLabel(null)).toBe("Review status unavailable");
  });

  it("reports missing evidence for null, empty, and incomplete fixtures only", () => {
    expect(formatMissingEvidenceState(null)).toBe(MISSING_EVIDENCE_LABEL);
    expect(formatMissingEvidenceState([])).toBe(MISSING_EVIDENCE_LABEL);
    expect(formatMissingEvidenceState([""])).toBeNull();
    expect(formatMissingEvidenceState(["SQL-1"])).toBeNull();
  });
});
