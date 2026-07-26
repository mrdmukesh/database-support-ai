import type { EnvironmentType } from "../../models/connection";

const content: Record<EnvironmentType, { badge: string; title: string; message: string }> = {
  production: {
    badge: "Production",
    title: "Production Investigation",
    message: "To protect production systems, this investigation uses strict read-only controls. Some evidence may be limited, masked, filtered, or blocked. The final result may contain evidence gaps.",
  },
  uat: {
    badge: "UAT",
    title: "Non-Production Investigation",
    message: "Broader bounded read-only evidence collection is enabled. Data and schema modifications remain prohibited.",
  },
  test: {
    badge: "Test",
    title: "Non-Production Investigation",
    message: "Broader bounded read-only evidence collection is enabled. Data and schema modifications remain prohibited.",
  },
  evaluation: {
    badge: "Demo / Evaluation",
    title: "Evaluation Investigation",
    message: "This environment is intended for testing and benchmarking. Broader bounded read-only scans, metadata discovery, and relationship analysis are enabled. Data and schema modifications remain prohibited.",
  },
  demo: {
    badge: "Demo / Evaluation",
    title: "Evaluation Investigation",
    message: "This environment is intended for testing and benchmarking. Broader bounded read-only scans, metadata discovery, and relationship analysis are enabled. Data and schema modifications remain prohibited.",
  },
};

export function environmentLabel(environment: string): string {
  return content[environment as EnvironmentType]?.badge ?? "Production";
}

export function EnvironmentNotice({ environment }: { environment: EnvironmentType | string | undefined }) {
  const normalized = environment && environment in content ? environment as EnvironmentType : "production";
  const item = content[normalized];
  return (
    <aside className={`environment-notice environment-${normalized}`} aria-label={`${item.badge} investigation policy`}>
      <strong className="environment-badge">{item.badge}</strong>
      <div><h3>{item.title}</h3><p>{item.message}</p></div>
    </aside>
  );
}
