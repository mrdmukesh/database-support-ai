interface RecommendationSectionProps { recommendations: readonly unknown[] | null | undefined }

export function RecommendationSection({ recommendations }: RecommendationSectionProps) {
  const items = (recommendations ?? []).flatMap((item) => {
    const text = typeof item === "string" ? item.trim() : "";
    return text ? [text] : [];
  });
  const status = items.some((item) => /no corrective action|not recommended/i.test(item)) ? "Not recommended" : items.length ? "Proposed" : "Pending";
  return (
    <section aria-labelledby="recommendation-title">
      <header className="result-section-heading"><h3 id="recommendation-title">Recommended Next Step</h3><span className="ui-badge">{status}</span></header>
      {items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : (
        <p>Download the report and run suggested verification checks before applying changes.</p>
      )}
    </section>
  );
}
