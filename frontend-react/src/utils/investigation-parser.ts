export interface LegacyInvestigationMessage {
  raw: string;
  investigationId: string;
  investigationMode: string;
  detectedIntent: string;
  aiAssistedReasoning: string;
  reason: string;
  rootCauses: string[];
  confirmedFacts: string[];
  recommendations: string[];
}

/** Convert unknown legacy content to text without interpreting or enriching it. */
export function investigationText(value: unknown): string {
  return value == null ? "" : String(value);
}

/** Extract a case-insensitive `Label: value` line from legacy assistant text. */
export function extractFirstLine(content: unknown, label: string): string {
  if (!label) return "";
  const escapedLabel = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = investigationText(content).match(new RegExp(`^${escapedLabel}:\\s*(.+)$`, "mi"));
  return match ? match[1].trim() : "";
}

/** Return the body below an exact `## Title` marker, stopping at the next H2. */
export function extractSection(content: unknown, title: string): string {
  if (!title) return "";
  const marker = `## ${title}`;
  const text = investigationText(content);
  const start = text.indexOf(marker);
  if (start < 0) return "";
  const after = text.slice(start + marker.length);
  const end = after.search(/\n##\s+/);
  return (end >= 0 ? after.slice(0, end) : after).trim();
}

/** Extract non-empty Markdown dash bullets, preserving their text and order. */
export function extractBullets(content: unknown, limit = Number.POSITIVE_INFINITY): string[] {
  if (limit <= 0) return [];
  return investigationText(content)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith("- "))
    .map((line) => line.slice(2).trim())
    .filter(Boolean)
    .slice(0, limit);
}

export function extractSectionBullets(content: unknown, title: string, limit = 4): string[] {
  return extractBullets(extractSection(content, title), limit);
}

/** Parse the fields used by the legacy investigation summary without inventing data. */
export function parseLegacyAssistantMessage(content: unknown): LegacyInvestigationMessage {
  const raw = investigationText(content).trim();
  return {
    raw,
    investigationId: extractFirstLine(raw, "Investigation ID"),
    investigationMode: extractFirstLine(raw, "Investigation Mode"),
    detectedIntent: extractFirstLine(raw, "Detected Intent"),
    aiAssistedReasoning: extractFirstLine(raw, "AI-assisted reasoning"),
    reason: extractFirstLine(raw, "Reason"),
    rootCauses: extractSectionBullets(raw, "Root Cause Analysis", 3),
    confirmedFacts: extractSectionBullets(raw, "Confirmed Facts", 3),
    recommendations: extractSectionBullets(raw, "Recommendation", 4),
  };
}
