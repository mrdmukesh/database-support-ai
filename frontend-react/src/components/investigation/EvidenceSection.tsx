import { MISSING_EVIDENCE_LABEL } from "../../utils/investigation-formatters";

interface EvidenceSectionProps { evidence: readonly unknown[] | null | undefined }

export function EvidenceSection({ evidence }: EvidenceSectionProps) {
  const items = (evidence ?? []).flatMap((item) => {
    const text = typeof item === "string" ? item.trim() : "";
    return text ? [text] : [];
  });
  return (
    <section aria-labelledby="evidence-title">
      <h3 id="evidence-title">Confirmed Evidence</h3>
      {items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : (
        <p>{MISSING_EVIDENCE_LABEL}</p>
      )}
    </section>
  );
}
