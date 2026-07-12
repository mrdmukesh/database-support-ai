import { useParams } from "react-router-dom";

function MigrationPlaceholder({ title }: { title: string }) {
  return (
    <section className="startup-card" aria-labelledby="placeholder-title">
      <p className="eyebrow">React migration placeholder</p>
      <h1 id="placeholder-title">{title}</h1>
      <p>This route is reserved for migration. Existing application functionality has not moved here yet.</p>
    </section>
  );
}

export function InvestigationsPage() {
  return <MigrationPlaceholder title="Investigations" />;
}

export function InvestigationDetailPage() {
  const { investigationId } = useParams();
  return <MigrationPlaceholder title={`Investigation ${investigationId ?? ""}`.trim()} />;
}

export function LearningPage() {
  return <MigrationPlaceholder title="Learning" />;
}

export function NotFoundPage() {
  return <MigrationPlaceholder title="Page not found" />;
}
