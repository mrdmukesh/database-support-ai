# Database Support AI Developer Flow

Owner: Mukesh Dabi

## 1. End-to-End Request Flow

1. User signs in and selects a workspace.
2. User creates or selects an active database connection.
3. User uploads optional documents such as runbooks, known issues, procedure notes, or process guides.
4. User asks a question from AI Chat.
5. `/chat/ask` validates organization/user/workspace access.
6. Intent and entities are extracted from the question.
7. Context discovery collects database metadata and workspace knowledge.
8. Safe SQL planning creates read-only evidence queries.
9. SafeSQLValidator and ProductionReadSafetyValidator approve or reject each query.
10. Evidence collector executes only validated read-only SQL.
11. Evidence gate checks whether the reported issue is reproduced.
12. Deterministic reasoning and optional LLM reasoning create the answer.
13. Verification checks are suggested but not executed automatically.
14. Report composer creates structured HTML, PDF, Word, and Excel reports.
15. Investigation, audit data, report links, and verification checks are stored.

## 2. Important Modules and Responsibilities

- `routers/chat.py`: main investigation orchestration, verification execution endpoints, and report regeneration.
- `agents/intent_agent.py`: classifies the user goal.
- `agents/entity_extraction_agent.py`: extracts business keys, procedure names, status codes, and search terms.
- `agents/context_discovery_agent.py`: combines metadata discovery and knowledge retrieval.
- `services/safe_sql_service.py`: creates read-only SQL and enforces SQL safety.
- `services/evidence_execution_service.py`: executes approved read-only SQL and stores returned rows as evidence.
- `services/evidence_gate_service.py`: blocks root-cause conclusions when the reported condition is not reproduced.
- `services/evidence_verification_agent.py`: suggests human-approved verification checks and executes only approved checks.
- `services/llm_reasoning_service.py`: optionally improves narrative quality using OpenAI over collected evidence only.
- `services/rag_retrieval_service.py`: indexes uploaded/approved knowledge and retrieves relevant chunks.
- `agents/report_composer_agent.py`: builds the structured report object.
- `reports/*_generator.py`: renders HTML, PDF, Word, and Excel outputs.
- `security/access_control.py`: workspace RBAC checks.
- `services/audit_service.py`: non-blocking audit log writes.
- `services/secrets_service.py`: local or Azure Key Vault secret storage.

## 3. How Investigation Is Generated

The investigation is database-generic. It does not hardcode clinic, ERP, shipping, school, or finance objects.

The engine derives target objects from:

- Question wording.
- Extracted business keys and terms.
- Table/column/procedure metadata.
- Relationships and foreign keys.
- Procedure read/write analysis.
- Uploaded documents and approved knowledge.
- Returned SQL evidence.

The final root-cause narrative should use confirmed evidence first, then strong inferences, then hypotheses.

## 4. How Verification Checks Are Generated

After the initial report, `suggest_verification_checks()` creates pending checks with:

- Claim to verify.
- Purpose.
- Claim being verified.
- Evidence logic.
- Expected result and plain-English meaning.
- Interpretation guidance.
- Safe read-only SQL.
- Risk/source/status.

The user must click `Run this check` or `Run all safe checks`. The app validates the SQL again before execution.

## 5. How Reports Are Produced

`compose_report()` converts a `DynamicInvestigationBundle` into an `InvestigationReport`.

The report generators then create:

- HTML report.
- PDF report.
- Word document.
- Excel workbook.

When verification checks are run, `_regenerate_report_with_verification()` replaces the verification sections and writes updated downloadable files.

## 6. How AI Reasoning Is Safely Applied

OpenAI is optional and controlled by `AI_REASONING_ENABLED`.

When enabled and configured:

- The deterministic engine still performs intent detection, metadata discovery, SQL planning, SQL validation, and evidence collection.
- OpenAI receives only the evidence package.
- The LLM cannot connect to the database.
- The LLM cannot execute SQL.
- The LLM cannot override SQL evidence.
- If the LLM fails or lacks evidence citations, deterministic reasoning is used.

## 7. RBAC, Audit, and Secrets

RBAC:

- `require_workspace_access()` and `require_resource_owner_workspace()` protect workspace-scoped resources.
- Enterprise RBAC is controlled by `FEATURE_ENTERPRISE_RBAC_ENABLED`.

Audit:

- `record_audit_event()` records important actions such as investigation run, verification SQL run, report download, document upload, and knowledge approval.
- Audit failures are logged and do not break user workflows.

Secrets:

- `SecretStore` abstracts local storage and Azure Key Vault.
- Production should store secret references, not raw passwords.
- API responses should never return database passwords or full connection strings with credentials.

## 8. How to Add a New Database Adapter

1. Add a new adapter class in `db/adapters.py`.
2. Implement metadata functions: tables, views, columns, indexes, foreign keys, primary keys.
3. Implement procedure listing/definition if the database supports procedures.
4. Implement row estimates and EXPLAIN behavior when possible.
5. Add the engine mapping to `adapter_for()`.
6. Confirm `execute_read_only_query()` only receives SQL already approved by SafeSQLValidator.
7. Add tests for metadata discovery, safe query execution, and procedure analysis.

## 9. How to Add a New Verification Check Type

1. Add a suggestion helper in `services/evidence_verification_agent.py`.
2. Return `SuggestedVerificationCheck` with claim, SQL, expected result, source, and explanation fields.
3. Ensure generated SQL is SELECT, SHOW, DESCRIBE, DESC, or EXPLAIN only.
4. Add result interpretation to `_status_from_expected()` only if a new expected-result pattern is needed.
5. Add tests proving unsafe SQL is rejected and approved SQL returns the expected status.

## 10. Troubleshooting Common Failures

- `Unsafe SQL command rejected`: generated or edited SQL did not pass SafeSQLValidator. Check for write commands, stored procedure execution, locks, or multiple statements.
- `Failed to fetch`: frontend cannot reach the API or the deployed API returned a non-JSON error. Check app URL, backend logs, and CORS/reverse proxy routing.
- `No verification checks were suggested`: investigation may not have collected enough evidence or verification agent feature flag is disabled.
- `Report template not found`: confirm templates are included in package/deployment image.
- `OpenAI disabled`: check `AI_REASONING_ENABLED`, `LLM_PROVIDER`, and `OPENAI_API_KEY`.
- `No documents used`: confirm document upload succeeded, indexing completed, and workspace ids match.
- `Cross-workspace access denied`: confirm workspace membership and `FEATURE_ENTERPRISE_RBAC_ENABLED`.
- `Database connection timeout`: check firewall, SSL mode, credentials, database server state, and Azure networking.
