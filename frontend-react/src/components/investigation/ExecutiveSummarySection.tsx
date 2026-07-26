import { useMemo, useState } from "react";
import { formatSafeText } from "../../utils/investigation-formatters";

const KNOWN_LABELS = [
  "Senior engineer explanation",
  "Clearer report wording",
  "Confidence note",
  "Recommended next questions",
  "Evidence gaps",
  "Verified findings",
];

type SummaryPart = { label: string; body: string };

function splitSentences(text: string) {
  return text.split(/(?<=[.!?])\s+/).map((item) => item.trim()).filter(Boolean);
}

function formatExecutiveSummary(value: unknown): SummaryPart[] {
  const text = formatSafeText(value, "Summary unavailable for this investigation.").trim();
  const markers = KNOWN_LABELS
    .map((label) => ({ label, index: text.toLowerCase().indexOf(`${label.toLowerCase()}:`) }))
    .filter((marker) => marker.index >= 0)
    .sort((a, b) => a.index - b.index);
  if (!markers.length) return [{ label: "Investigation summary", body: text }];
  const parts: SummaryPart[] = [];
  if (markers[0].index > 0) parts.push({ label: "Verified findings", body: text.slice(0, markers[0].index).trim() });
  markers.forEach((marker, index) => {
    const start = marker.index + marker.label.length + 1;
    const end = markers[index + 1]?.index ?? text.length;
    const body = text.slice(start, end).trim();
    if (body) parts.push({ label: marker.label.replace(" note", ""), body });
  });
  return parts;
}

function SummaryBody({ parts }: { parts: SummaryPart[] }) {
  return <div className="executive-summary-full">
    {parts.map((part) => <section key={`${part.label}-${part.body.slice(0, 24)}`}>
      <h4>{part.label}</h4>
      {part.label === "Recommended next questions"
        ? <ul>{splitSentences(part.body).map((item) => <li key={item}>{item}</li>)}</ul>
        : splitSentences(part.body).map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
    </section>)}
  </div>;
}

export function ExecutiveSummarySection({ summary }: { summary: unknown }) {
  const [expanded, setExpanded] = useState(false);
  const fullText = formatSafeText(summary, "Summary unavailable for this investigation.").trim();
  const parts = useMemo(() => formatExecutiveSummary(fullText), [fullText]);
  const sentences = useMemo(() => splitSentences(fullText), [fullText]);
  const isLong = fullText.length > 700 || sentences.length > 5;
  const collapsed = sentences.slice(0, 5).join(" ").slice(0, 700).trim();
  const brief = [
    { label: "Outcome", text: sentences[0] },
    { label: "Verified finding", text: sentences.find((item) => /\b(verified|evidence|rows?|records?)\b/i.test(item)) },
    { label: "Root-cause status", text: sentences.find((item) => /root cause/i.test(item)) },
    { label: "Evidence gap", text: sentences.find((item) => /\b(gap|missing|unavailable|could not|cannot|not establish)/i.test(item)) },
  ].filter((item, index, all) => item.text && all.findIndex((candidate) => candidate.text === item.text) === index);

  return (
    <section className="executive-summary-card result-card-wide" aria-labelledby="executive-summary-title">
      <header><div><p className="eyebrow">Decision brief</p><h3 id="executive-summary-title">Executive Summary</h3></div>
        {isLong ? <span className="ui-badge" data-tone="neutral">{expanded ? "Full summary" : "Concise view"}</span> : null}
      </header>
      {isLong && !expanded
        ? <div className="executive-summary-collapsed">
          {brief.length > 1 ? brief.map((item) => <section key={item.label}><h4>{item.label}</h4><p>{item.text}</p></section>)
            : <section><h4>Outcome and verified findings</h4><p>{collapsed}{collapsed.length < fullText.length ? "…" : ""}</p></section>}
        </div>
        : <SummaryBody parts={parts} />}
      {isLong ? <button type="button" className="summary-toggle ui-button ui-button-secondary no-print"
        aria-expanded={expanded} aria-controls="executive-summary-detail"
        onClick={() => setExpanded((value) => !value)}>
        {expanded ? "Show less" : "Read more"}
      </button> : null}
      {isLong ? <div id="executive-summary-detail" className="print-only"><SummaryBody parts={parts} /></div> : null}
    </section>
  );
}
