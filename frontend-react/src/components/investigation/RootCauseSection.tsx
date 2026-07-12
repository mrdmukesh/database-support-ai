interface RootCauseSectionProps { rootCauses: readonly unknown[] | null | undefined }

export function RootCauseSection({ rootCauses }: RootCauseSectionProps) {
  const items = cleanItems(rootCauses);
  return (
    <section aria-labelledby="root-cause-title">
      <h3 id="root-cause-title">Most Likely Root Cause</h3>
      {items.length ? <ul>{items.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul> : (
        <p>Open the report for full evidence-backed root-cause analysis.</p>
      )}
    </section>
  );
}

function cleanItems(items: readonly unknown[] | null | undefined): string[] {
  return (items ?? []).flatMap((item) => {
    const text = typeof item === "string" ? item.trim() : "";
    return text ? [text] : [];
  });
}
