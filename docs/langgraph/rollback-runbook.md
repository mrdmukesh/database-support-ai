# LangGraph rollback runbook

LangGraph is the only supported execution engine. A workflow-engine fallback is not available.

For an incident, stop or roll back the affected application revision using the normal Azure
revision controls, preserve evidence/report/audit records, and restore the last reviewed
LangGraph-only image. Verify graph compilation, readiness, authorization, SQL safety, evidence
auditing, report retrieval, and `LANGGRAPH` execution metadata before restoring traffic.

Never use configuration to select Legacy, shadow, or compare execution.
