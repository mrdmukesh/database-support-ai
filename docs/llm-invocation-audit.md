# LLM Invocation Audit

The LLM Invocation Audit is a read-only administrator surface for troubleshooting,
observability, research, and usage analysis. It records one row for every actual
provider attempt, including retries, at the shared OpenAI Responses API boundary.

## Architecture

- `llm_invocation_audit` stores sanitized prompts, context, responses, errors,
  timing, token usage, prompt-version identity, tracing identifiers, and SHA-256
  hashes of the original request and response payloads.
- Raw unredacted payloads are never stored. The existing `sanitize_ai_trace`
  masking layer runs before every text payload is assigned to an audit field.
- Audit writes use nested transactions and best-effort exception handling. A
  persistence failure is logged only by exception type and never fails the
  investigation or exposes payload content.
- Each provider retry is a separate row linked by `logical_request_id`.
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

## Retention

`LLM_AUDIT_RETENTION_DAYS` defaults to 365 days. Cleanup must be invoked by the
approved maintenance scheduler under the application's retention/legal-hold
policy; the admin UI intentionally exposes no deletion control.
