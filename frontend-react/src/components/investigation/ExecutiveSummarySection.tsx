import { formatSafeText } from "../../utils/investigation-formatters";

export function ExecutiveSummarySection({ summary }: { summary: unknown }) {
  return (
    <section aria-labelledby="executive-summary-title">
      <h3 id="executive-summary-title">Executive Summary</h3>
      <pre>{formatSafeText(summary, "Summary unavailable for this investigation.")}</pre>
    </section>
  );
}
