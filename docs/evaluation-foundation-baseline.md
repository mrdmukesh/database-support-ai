# Evaluation foundation baseline

Recorded before implementation on 2026-07-14.

- Git commit: `a9cb4cfaf1c66581c0dfd97da0d8326fd9048405`
- Application/package version: `0.1.0`
- Branch created for this work: `feature/evaluation-foundation`
- Backend baseline: 663 tests collected; 649 passed; 14 setup errors; no assertion failures.
- Frontend baseline: unable to start because Vite could not write `frontend-react/node_modules/.vite-temp` (`EPERM`).

## Current investigation contracts

`POST /chat/ask` accepts `ChatAskRequest`: `organization_id`, `workspace_id`, `connection_id`,
`user_id`, `question`, and optional `conversation_id`. It returns `ChatAskResponse`: conversation,
user and assistant messages, findings, confidence, human-review requirement, sources, report links,
optional investigation ID, connection ID, and connection name. Saved investigation summaries expose
identity/scope, connection, question, intent, answer, confidence, report path, status, and creation time.

## Relevant feature flags and controls

- `AI_REASONING_ENABLED` / legacy alias `LLM_ENABLED` (default false)
- `AI_DEBUG_TRACE_ENABLED` (default false)
- `VERIFICATION_AGENT_ENABLED` (default true)
- `KNOWLEDGE_RETRIEVER_BACKEND` and `EMBEDDING_PROVIDER` (default local)
- `MAX_INVESTIGATION_ROWS` (default 100) and `ALLOW_FULL_TABLE_SCAN` (default false)
- `FEATURE_ENTERPRISE_RBAC_ENABLED` (default false)
- `FEATURE_AUDIT_LOGGING_ENABLED` (default true)
- `FEATURE_KEYVAULT_SECRETS_ENABLED` (default false)

## Reuse boundary

The evaluation layer reuses the SQLAlchemy base/mixins and session conventions, persisted
investigation identifiers/snapshots, evidence/citation vocabulary, read-only SQL safety concepts,
and benchmark structure. It does not alter or wrap the production reasoning, LLM, RAG, report, API,
or frontend code paths in this foundation phase.
