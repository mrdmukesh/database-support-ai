import { Link } from "react-router-dom";
import type { InvestigationSummary } from "../../models/investigation";
export function InvestigationHistoryList({ investigations }: { investigations: readonly InvestigationSummary[] }) {
  if (!investigations.length) return <p>No saved investigations.</p>;
  return <table><thead><tr><th>Question</th><th>Intent</th><th>Status</th><th>Created</th><th>Action</th></tr></thead>
    <tbody>{investigations.map((item) => <tr key={item.id}><td>{item.user_question}</td><td>{item.detected_intent}</td><td>{item.status}</td><td>{item.created_at}</td><td><Link to={`/app/investigations/${encodeURIComponent(item.id)}`}>Open</Link></td></tr>)}</tbody></table>;
}
