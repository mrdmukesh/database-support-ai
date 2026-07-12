interface RecommendationSectionProps { recommendations: readonly unknown[] | null | undefined }

export function RecommendationSection({ recommendations }: RecommendationSectionProps) {
  const items = (recommendations ?? []).flatMap((item) => {
    const text = typeof item === "string" ? item.trim() : "";
    return text ? [text] : [];
  });
  return (
    <section aria-labelledby="recommendation-title">
      <h3 id="recommendation-title">Recommended Next Step</h3>
      {items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : (
        <p>Download the report and run suggested verification checks before applying changes.</p>
      )}
    </section>
  );
}
