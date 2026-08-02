import { formatSafeText } from "../../utils/investigation-formatters";
interface StructuredResult { columns?: string[]; rows?: Record<string, unknown>[]; row_count?: number }
interface Props { actualResult?: unknown; structuredResult?: StructuredResult; confidenceImpact?: unknown; status?: unknown; notes?: unknown }
const displayValue = (value: unknown) => value === null ? "NULL" : formatSafeText(value, "");
export function VerificationResult({ actualResult, structuredResult, confidenceImpact, status, notes }: Props) {
  const columns = structuredResult?.columns ?? [];
  const rows = structuredResult?.rows ?? [];
  return <section aria-label="Verification result">
    <dl>
      <dt>Status</dt><dd>{formatSafeText(status, "Pending")}</dd>
      <dt>Actual result</dt><dd>
        {columns.length ? <><table><thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
          <tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{displayValue(row[column])}</td>)}</tr>)}</tbody></table>
          <span>{structuredResult?.row_count ?? rows.length} row(s) returned</span></> : formatSafeText(actualResult, "No result recorded.")}
      </dd>
      <dt>Confidence impact</dt><dd>{formatSafeText(confidenceImpact, "Not recorded")}</dd>
      <dt>Notes</dt><dd>{formatSafeText(notes, "No notes")}</dd>
    </dl>
  </section>;
}
