# Current Investigation Flow (LangGraph Baseline)

This document records the investigation architecture on `main` commit
`47dad9433529c5232165e92b232c4eb68084a284` before LangGraph integration.
It describes the existing behavior; it does not propose or introduce runtime changes.

## Entry points and execution ownership

### Production investigation API

- `src/legacydb_copilot/api.py::create_fastapi_app` constructs the FastAPI application and
  includes the chat and investigation-state routers.
- `src/legacydb_copilot/routers/chat.py::ask_chat_question` is the public investigation entry
  point (`POST /chat/ask`). It authenticates the caller, checks organization/user identity with
  `assert_same_organization` and `assert_same_user`, and authorizes the workspace with
  `require_workspace_access(..., action="investigate")`.
- `src/legacydb_copilot/routers/chat.py::_run_dynamic_investigation` is the main synchronous
  orchestration function. The request remains in the API process until evidence collection,
  reasoning, report generation, and persistence finish.
- `src/legacydb_copilot/routers/learning.py::get_investigation` reads a persisted investigation.
  `src/legacydb_copilot/routers/investigation_states.py::current_investigation_state`,
  `investigation_state_history`, and `investigation_progress` expose state and progress, with
  `::_investigation` enforcing resource/workspace authorization.

There is no production investigation background-worker handoff in the current `/chat/ask` path.

### Evaluation background worker

- `evaluation/worker.py::build_worker` creates the durable evaluation worker and
  `evaluation/worker.py::run_worker` runs its polling loop.
- `src/legacydb_copilot/services/evaluation_job_worker.py::EvaluationJobWorker.run_once` claims,
  preflights, executes, updates progress for, and completes an evaluation job.
- `src/legacydb_copilot/services/evaluation_worker_runtime.py::EvaluationWorkerRuntime` optionally
  hosts that evaluation worker with the API runtime.
- These components run protected benchmarks/evaluations. They are not the production
  investigation orchestrator and must remain isolated from application investigation state.

## Current synchronous execution sequence

1. **Authorization, environment, and policy**
   - `routers/chat.py::ask_chat_question` validates tenant, user, and workspace access.
   - `services/environment_resolution_service.py::resolve_environment` produces the authoritative
     environment snapshot.
   - `services/scan_policy_service.py::resolve_connection_scan_policy` selects row/full-scan
     policy before any investigation query is run.
   - `routers/chat.py::_find_workspace_connection` resolves only the selected workspace connection.

2. **Prompt safety and conversation**
   - `routers/chat.py::_get_or_create_conversation` establishes chat history.
   - `ai.py::analyze_prompt` rejects unsafe prompt paths before dynamic investigation.

3. **Intent, entities, and investigation mode**
   - `agents/intent_agent.py::detect_intent` classifies the question.
   - `agents/entity_extraction_agent.py::extract_entities` extracts business identifiers.
   - `services/investigation_mode_service.py::classify_investigation_mode` routes metadata
     validation, knowledge search, business-rule discovery, or full live investigation.

4. **Connection and metadata discovery**
   - `routers/chat.py::_build_connection_string` and
     `db/connector.py::ConnectionPool.get_or_create` establish the selected connector.
   - `routers/chat.py::_load_and_validate_active_schema` validates the connected database and
     loads its schema.
   - `agents/context_discovery_agent.py::discover_context` coordinates live metadata and document
     context. Its metadata path uses `services/metadata_search_service.py::search_metadata`.
   - `services/metadata_search_service.py::resolve_qualified_object_names` and
     `::query_relevance_terms` support exact object resolution and ranking context.

5. **Entity resolution**
   - `services/entity_resolution_service.py::resolution_metadata_for_schema` builds the bounded
     resolver scope.
   - `services/entity_resolution_service.py::resolve_entities` resolves identifiers through
     validated, bounded, read-only evidence queries.
   - `routers/chat.py::_apply_entity_resolutions` applies only a resolvable result; ambiguous,
     missing, or blocked results return a non-speculative answer.
   - `services/entity_resolution_service.py::metadata_with_resolved_tables` promotes
     database-proven tables into downstream evidence scope.

6. **Object ranking and procedure inspection**
   - `agents/object_ranking_agent.py::rank_relevant_objects` ranks discovered objects.
   - `services/stored_procedure_intelligence.py::analyze_stored_procedures` inspects definitions;
     procedures are not executed.

7. **Investigation planning and SQL generation**
   - `agents/investigation_planner_agent.py::build_investigation_plan` is the current planner
     entry point.
   - It reuses `services/safe_sql_service.py::plan_safe_queries`, which emits `PlannedQuery`
     records and explicitly forbids mutation statements and stored-procedure execution.
- `services/safe_investigation_planner.py::SafeInvestigationPlanner.select_next` is the bounded,
     policy-aware action selector used by the reusable agentic loop.

8. **SQL validation, bounding, and execution**
   - `services/safe_sql_service.py::validate_read_only_sql` is the central read-only validator.
   - `services/safe_sql_service.py::ProductionReadSafetyValidator.validate` applies scan policy,
     row limits, and production protections.
   - `services/evidence_execution_service.py::execute_evidence_plan` validates every query again,
     applies policy/limits, executes it, and creates normalized `EvidenceResult` records.
   - `services/evidence_execution_service.py::_execute_read_only_query` calls the connector’s
     read-only execution API.
   - `db/connector.py::DatabaseConnector.execute_select_query` and
     `::execute_read_only_query` delegate to database adapters with a result limit. Connector
     setup also applies configured query timeouts.

9. **Evidence enrichment and Evidence Gate**
   - `services/evidence_correlation_service.py::correlate_evidence` correlates SQL, procedure, and
     document evidence.
   - `services/evidence_focus_service.py::build_evidence_focus` identifies the affected entity,
     business key, and relevant evidence.
   - `services/evidence_gate_service.py::run_evidence_gate` determines whether the reported
     condition is reproduced and whether verified evidence permits reasoning.
   - `services/evidence_gap_detection_service.py::detect_evidence_gaps` records missing evidence.
   - `services/reasoning_dispatch_service.py::dispatch_reasoning` converts the Evidence Gate
     result into a deterministic reasoning permission/mode decision.

10. **Deterministic and LLM reasoning**
    - `agents/reasoning_agent.py::reason_about_evidence` creates evidence-grounded deterministic
      conclusions when the gate permits normal root-cause reasoning.
    - `services/evidence_gate_service.py::unreproduced_reasoning` supplies the non-reproduced or
      insufficient-evidence branch.
    - `services/llm_reasoning_service.py::enhance_reasoning_with_llm` optionally enhances the
      deterministic result only when `dispatch_reasoning` permits it.
    - `services/llm_invocation_audit_service.py::LLMInvocationAuditService` and
      `::InvocationContext` preserve per-stage LLM invocation audit, prompt/payload hashes,
      outcomes, and investigation/workspace correlation.

11. **Recommendations, verification, and reporting**
    - `agents/recommendation_agent.py::recommend_actions` produces recommendations. Mutation SQL
      remains recommendation-only and is never auto-executed.
    - `services/evidence_verification_agent.py::suggest_verification_checks` proposes additional
      read-only checks.
    - `agents/report_composer_agent.py::compose_report` creates the structured report.
    - `services/investigation_reports.py::generate_investigation_report_files` renders report
      artifacts and `::report_storage_references` records storage locations.

12. **Persistence and audit**
    - `routers/chat.py::ask_chat_question` persists `InvestigationModel`, chat messages, report
      snapshot/storage references, serialized evidence (`evidence_json`), evidence-gap analysis,
      sanitized AI trace, environment/policy snapshots, and verification checks in one database
      session.
    - `db/models.py::InvestigationModel` is the investigation aggregate.
    - Evidence audit detail is retained in `InvestigationModel.evidence_json` and the sanitized
      `InvestigationModel.ai_debug_trace_json`; each serialized `EvidenceResult` includes its
      evidence id, purpose, SQL, rows/status, semantics, relevance, scan-policy decision, and error.
    - `services/verified_evidence_service.py::normalize_verified_evidence` derives the verified
      evidence count, categories, and gaps used by the reasoning gate and terminal trace.
    - `services/audit_service.py::record_audit_event` records investigation and state-transition
      audit events. `ask_chat_question` records `INVESTIGATION_STARTED`.

## Agentic workflow and progress tracking already present

- `services/agentic_investigation_loop.py::MultiStepAgenticInvestigationLoop.run` implements a
  reusable bounded loop:
  assessment -> gap identification -> action selection -> planning -> validation -> execution ->
  verification -> state update -> stop evaluation.
- `services/agentic_investigation_loop.py::DeterministicSQLPipeline` adapts that loop to the
  existing `plan_safe_queries`, `validate_read_only_sql`, and `execute_evidence_plan` services.
- `services/safe_investigation_planner.py::SafeInvestigationPlanner` enforces environment policy,
  scope, novelty, and budget decisions.
- `services/investigation_state_machine.py::InvestigationStateService.initialize`,
  `::transition`, `::cancel`, and `::fail` persist ordered transitions to
  `InvestigationStateTransitionModel` and audit them.
- `InvestigationAgenticStepModel` stores per-iteration planner/action/result records.
- `routers/investigation_states.py::investigation_progress` assembles current state, transitions,
  agentic steps, gap analysis, entity resolution, hypothesis verification, execution path, and
  fix-readiness data.
- On the current API path, `Settings.feature_agentic_investigation_enabled` causes
  `ask_chat_question` to initialize state tracking and call
  `terminal_outcome_service.py::resolve_canonical_terminal_outcome` /
  `::persist_canonical_terminal_outcome` **after** the existing synchronous investigation has
  completed. The reusable multi-step loop is not yet the primary `/chat/ask` orchestrator.

`services/investigation_state_machine.py::TERMINAL_STATES` defines:

- `ROOT_CAUSE_CONFIRMED`
- `ISSUE_NOT_REPRODUCED`
- `INSUFFICIENT_EVIDENCE`
- `BLOCKED_BY_MISSING_SOURCE`
- `QUERY_BUDGET_EXHAUSTED`
- `ITERATION_BUDGET_EXHAUSTED`
- `POLICY_BLOCKED`
- `FAILED`
- `CANCELLED`

The legacy persisted workflow statuses consumed by evaluation are listed in
`evaluation/runners/runner.py::TERMINAL_STATUSES`.

## Evaluation and benchmark entry points

- `evaluation/cli/__main__.py::main` / `::execute` are the general evaluation CLI.
- `evaluation/runners/runner.py::EvaluationRunner.run_scenario` and `::run_many` isolate database
  setup/injection, call the public investigation API, poll/read results, score, persist, and clean
  up.
- `evaluation/worker.py::run_worker` plus
  `services/evaluation_job_worker.py::EvaluationJobWorker` provide durable background execution.
- `evaluation/agentic_benchmark/__main__.py::execute` runs the protected agentic benchmark;
  expected answers remain scorer-only.
- `evaluation/demo_payroll_benchmark/__main__.py::execute` runs the focused demo-payroll pack
  through a reader-only/no-mutation lifecycle.
- `src/legacydb_copilot/benchmark_cli.py::main` is the legacy application benchmark CLI.

## LangGraph integration points

The narrowest future orchestration seam is around `_run_dynamic_investigation`, while retaining
the existing domain services as graph-node implementations:

| Graph concern | Existing integration point to reuse |
|---|---|
| API admission and authorization | `routers/chat.py::ask_chat_question` |
| Environment/policy snapshot | `resolve_environment`, `resolve_connection_scan_policy` |
| Intent/entity preparation | `detect_intent`, `extract_entities`, `resolve_entities` |
| Metadata node | `discover_context`, `search_metadata` |
| Planner node | `build_investigation_plan`, `SafeInvestigationPlanner.select_next` |
| SQL validation node | `validate_read_only_sql`, `ProductionReadSafetyValidator.validate` |
| Execution node | `execute_evidence_plan` |
| Evidence verification/gate node | `build_evidence_focus`, `run_evidence_gate` |
| Reasoning node | `dispatch_reasoning`, `reason_about_evidence`, `enhance_reasoning_with_llm` |
| Report node | `compose_report`, `generate_investigation_report_files` |
| Checkpoint/progress mapping | `InvestigationStateService`, state/step persistence models |
| Terminal mapping | `resolve_canonical_terminal_outcome`, `TERMINAL_STATES` |
| Audit/persistence | `record_audit_event`, verified evidence and LLM invocation audit services |

Any LangGraph integration must continue to route all SQL through the existing validation and
bounded execution services, keep workspace authorization at API admission and resource reads,
retain evidence and LLM audit correlation, and leave protected evaluation data outside the
production graph state.
