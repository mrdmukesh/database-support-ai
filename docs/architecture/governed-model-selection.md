# Governed model selection

## Architecture

Model selection is a server-authorized policy decision between the authenticated investigation
request and the LLM provider boundary. The browser sends only a selection mode and/or catalog
record ID. It cannot submit a provider model string.

The resolver loads one organization policy and intersects globally enabled/available models with
environment, workspace, application-role, user approval, retirement, premium-approval, and cost
ceiling rules. It returns an immutable invocation configuration containing provider, provider
model ID, reasoning effort, timeout, output limit, decision reason, and configuration version.
Only the reasoning provider settings receive that configuration. Evidence collection, SQL
validation, Evidence Gate, claim verification, confidence scoring, and report generation retain
their existing controls. Evaluation worker and AI-judge models remain independently configured.

## Data model

- `llm_model_catalog`: organization catalog and safe capability/operational metadata; never keys.
- `llm_model_policy`: default, Automatic candidates, fallback, environment/role and cost policy.
- `llm_model_role_entitlement`: role/model intersection.
- `llm_model_user_entitlement`: explicit grants and time-bounded premium approvals.
- `llm_model_workspace_entitlement`: workspace/model intersection.
- `llm_model_selection_audit`: requested/effective selection, candidates, routing factors and reason.
- `investigations`: immutable selection snapshot for historical reproducibility.

## Automatic routing

Automatic considers only authorized configured candidates. The initial deterministic rule chooses
the configured Fast category for routine questions and Deep Analysis for longer questions or
questions containing multiple configured complexity signals. A low-latency policy preference
always prefers Fast. The candidate set, factors, result, and reason are audited. No LLM performs
routing.

## Security and audit

Admin endpoints require `models:manage`; ordinary users receive only safe display metadata.
Provider identifiers are visible only in admin and persisted audit/history contracts. API keys and
provider credentials are neither stored in catalog records nor returned. Denials and explicitly
enabled fallbacks create selection-audit records.

## Known limitations

The initial resolver applies one model to investigation reasoning stages. Stage-specific routing
and a cross-model research export are intentionally deferred. Provider availability is currently
administrator-maintained; live provider probing remains the existing preflight responsibility.
