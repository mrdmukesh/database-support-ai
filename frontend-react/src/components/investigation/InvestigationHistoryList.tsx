import { Link } from "react-router-dom";
import type { InvestigationSummary } from "../../models/investigation";
import { EmptyState } from "../common/EmptyState";
import { StatusBadge } from "../common/StatusBadge";
export function InvestigationHistoryList({ investigations }: { investigations: readonly InvestigationSummary[] }) {
  if (!investigations.length) return <EmptyState message="No saved investigations." />;
  return <table><thead><tr><th scope="col">Question</th><th scope="col">Intent</th><th scope="col">Status</th><th scope="col">Created</th><th scope="col">Action</th></tr></thead>
    <tbody>{investigations.map((item) => <tr key={item.id}><td>{item.user_question}</td><td>{item.detected_intent}</td><td><StatusBadge status={item.status} /></td><td>{item.created_at}</td><td><Link to={`/app/investigations/${encodeURIComponent(item.id)}`}>Open</Link></td></tr>)}</tbody></table>;
}
