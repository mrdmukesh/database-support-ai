# LLM Invocation Audit

The LLM Invocation Audit is a read-only administrator surface for troubleshooting,
observability, research, and usage analysis. It records one row for every actual
provider attempt, including retries, at the shared OpenAI Responses API boundary.

## Architecture

- `AuditedLLMProviderClient` is the only HTTP boundary for OpenAI model,
  embedding, and AI Judge requests.
- `llm_invocation_audit` stores sanitized prompts, context, responses, errors,
  timing, token usage, prompt-version identity, tracing identifiers, and SHA-256
  hashes of the original request and response payloads.
- Raw unredacted payloads are never stored. The existing `sanitize_ai_trace`
  masking layer runs before every text payload is assigned to an audit field.
- Audit writes use nested transactions and best-effort exception handling. A
  persistence failure is logged only by exception type and never fails the
  investigation or exposes payload content.
- Each provider retry is a separate row linked by `logical_request_id`.
- Investigations also store `llm_audit_outcome` and `llm_audit_reason`. These
  explain a legitimate zero-invocation result without fabricating a provider row.
- List responses omit prompt and response bodies. Only the detail endpoint returns
  sanitized content.

## Authorization and APIs

The `admin.llm_audit.read` permission is granted to super administrators,
organization administrators, and auditors. Organization-scoped roles can only
read their own organization's records. Detail views are written to the existing
security audit log.

- `GET /admin/llm-invocations`
- `GET /admin/llm-invocations/{llm_invocation_id}`
- `GET /admin/investigations/{investigation_id}/llm-invocations`

There are no create, update, delete, retry, replay, or resubmit routes.

The list endpoint accepts `page`, `page_size`, `started_after`, `started_before`,
`investigation_id`, `workspace_id`, `stage_name`, `agent_name`, `model`,
`provider`, `status`, `user_id`, `min_duration_ms`, `failed_only`, and `search`.

## Administrator usage

Open **Administration → LLM Invocation Audit**. Filter the chronological list,
then select an invocation time to view its sanitized prompt, context, response,
usage, hashes, tracing data, and error details. Investigation details also contain
an admin-only **LLM Activity** section. Older investigations explicitly state that
audit data was not captured.

All displayed content is read-only. Copying content copies only the already
sanitized value returned by the API.

## Investigation stage inventory

Intent analysis, entity extraction, metadata discovery, relationship discovery,
safe SQL planning, SQL validation, evidence collection, evidence verification,
and report composition are deterministic in the application. They do not call a
text-generation model. Metadata discovery can call the embedding provider when
pgvector retrieval is enabled, and that request is audited under
`context_discovery_agent / Metadata Discovery`.

Root-cause reasoning calls the Responses API after the evidence gate and is
audited under `reasoning_agent / Root Cause Reasoning`. Every retry is a distinct
provider request and audit row. The evaluation AI Judge also uses the centralized
provider client; it retains its evaluation-specific audit records because it is
not an investigation stage and has no investigation ID.

If the evidence gate blocks reasoning, no provider row is created. The
investigation endpoint instead returns `AI_SKIPPED_BY_EVIDENCE_GATE` and its
sanitized explanation. Other supported outcomes include `DETERMINISTIC_ONLY`,
`ENTITY_RESOLUTION_FAILED`, `INVALID_CONFIGURATION`, and `PROVIDER_DISABLED`.

## Retention

`LLM_AUDIT_RETENTION_DAYS` defaults to 365 days. Cleanup must be invoked by the
approved maintenance scheduler under the application's retention/legal-hold
policy; the admin UI intentionally exposes no deletion control.
