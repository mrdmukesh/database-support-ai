import { describe, expect, it } from "vitest";
import {
  extractBullets,
  extractFirstLine,
  extractSection,
  extractSectionBullets,
  investigationText,
  parseLegacyAssistantMessage,
} from "./investigation-parser";

const legacy = `Investigation ID: INV-7
Investigation Mode: Evidence
Detected Intent: duplicate_data
AI-assisted reasoning: Enabled
Reason: Correlated SQL results

## Root Cause Analysis
- Retry execution caused duplicate processing.
- A second cause
- A third cause
- Must be limited out

## Confirmed Facts
- SQL-1 returned two rows.
- SQL-2 confirmed the retry.

## Recommendation
- Verify idempotency keys.
- Add monitoring.`;

describe("investigation parser", () => {
  it("converts null, undefined, empty, and scalar content deterministically", () => {
    expect(investigationText(null)).toBe("");
    expect(investigationText(undefined)).toBe("");
    expect(investigationText("")).toBe("");
    expect(investigationText(0)).toBe("0");
  });

  it("extracts labeled first lines case-insensitively and escapes malformed labels", () => {
    expect(extractFirstLine(legacy, "Investigation ID")).toBe("INV-7");
    expect(extractFirstLine("reason: kept", "Reason")).toBe("kept");
    expect(extractFirstLine("A+B: safe", "A+B")).toBe("safe");
    expect(extractFirstLine("Reason:", "Reason")).toBe("");
    expect(extractFirstLine(null, "Reason")).toBe("");
  });

  it("extracts exact legacy sections and preserves malformed or missing markers", () => {
    expect(extractSection(legacy, "Confirmed Facts")).toContain("SQL-1 returned two rows.");
    expect(extractSection("## Confirmed Facts\nunfinished", "Confirmed Facts")).toBe("unfinished");
    // Preserve the legacy indexOf behavior, including a marker embedded in a malformed H3.
    expect(extractSection("### Confirmed Facts\n- wrong heading", "Confirmed Facts")).toBe("- wrong heading");
    expect(extractSection(null, "Confirmed Facts")).toBe("");
  });

  it("extracts only dash bullets, removes empty bullets, and honors limits", () => {
    const malformed = "- first\r\n* ignored\r\n-   \r\n- second\r\nplain";
    expect(extractBullets(malformed)).toEqual(["first", "second"]);
    expect(extractBullets(malformed, 1)).toEqual(["first"]);
    expect(extractBullets(malformed, 0)).toEqual([]);
    expect(extractBullets(null)).toEqual([]);
  });

  it("extracts bullets from a named section only", () => {
    expect(extractSectionBullets(legacy, "Root Cause Analysis", 2)).toEqual([
      "Retry execution caused duplicate processing.", "A second cause",
    ]);
    expect(extractSectionBullets("malformed legacy text", "Root Cause Analysis")).toEqual([]);
  });

  it("parses complete legacy assistant messages with legacy limits", () => {
    const parsed = parseLegacyAssistantMessage(legacy);
    expect(parsed).toMatchObject({
      investigationId: "INV-7", investigationMode: "Evidence", detectedIntent: "duplicate_data",
      aiAssistedReasoning: "Enabled", reason: "Correlated SQL results",
    });
    expect(parsed.rootCauses).toHaveLength(3);
    expect(parsed.confirmedFacts).toEqual(["SQL-1 returned two rows.", "SQL-2 confirmed the retry."]);
  });

  it("preserves malformed raw content while returning empty structured fields", () => {
    expect(parseLegacyAssistantMessage("  malformed response {  ")).toEqual({
      raw: "malformed response {", investigationId: "", investigationMode: "", detectedIntent: "",
      aiAssistedReasoning: "", reason: "", rootCauses: [], confirmedFacts: [], recommendations: [],
    });
    expect(parseLegacyAssistantMessage(null).raw).toBe("");
  });
});
