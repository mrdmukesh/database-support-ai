import { formatSafeText } from "../../utils/investigation-formatters";

interface InvestigationHeaderProps {
  investigationId: unknown;
  question: unknown;
  intent?: unknown;
  status?: unknown;
  createdAt?: unknown;
}

export function InvestigationHeader({
  investigationId,
  question,
  intent,
  status,
  createdAt,
}: InvestigationHeaderProps) {
  return (
    <header className="investigation-header">
      <p className="eyebrow">Investigation result</p>
      <h2 id="investigation-result-title">
        Investigation {formatSafeText(investigationId, "ID unavailable")}
      </h2>
      <p>{formatSafeText(question, "Question unavailable")}</p>
      <dl>
        <dt>Intent</dt><dd>{formatSafeText(intent, "Unavailable")}</dd>
        <dt>Status</dt><dd>{formatSafeText(status, "Unavailable")}</dd>
        <dt>Created</dt><dd>{formatSafeText(createdAt, "Unavailable")}</dd>
      </dl>
    </header>
  );
}
