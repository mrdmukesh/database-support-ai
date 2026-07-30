# Investigation State Mapping

LG-03 defines a serializable state contract only. It does not create a `StateGraph`, graph nodes,
reducers, persistence migrations, or production integration.

## Existing-to-state mapping

| Existing model/type | LangGraph state field | Treatment | Reason |
|---|---|---|---|
| `db.models.InvestigationModel.id` | `investigation_id` | Reused concept | Preserves the existing aggregate identity; the factory never generates a replacement. |
| `InvestigationModel.workspace_id` | `workspace_id` | Reused concept | Maintains the workspace authorization and audit boundary. |
| `InvestigationModel.created_by_id` | `actor_id` | Adapted | Keeps audit identity without retaining a user/service instance. |
| `llm_invocation_audit_service.InvocationContext.correlation_id` | `correlation_id` | Reused concept | Preserves existing cross-stage audit correlation. |
| `InvestigationModel.created_at`, `updated_at` | `created_at`, `updated_at` | Reused concept | Serializable UTC timestamps for checkpoint/progress ordering. |
| `InvestigationModel.user_question` | `question` | Reused concept | Original validated request text. |
| `EnvironmentSnapshot` | `environment`, `requested_database` | Adapted | Retains safe identifiers only; no connection strings or credentials. |
| `scan_policy_service.ScanPolicy` | `environment_policy` | Adapted | `EnvironmentPolicyRecord` keeps policy name/version, safety profile, row/timeout limits, and full-scan decision. |
| `agents.intent_agent.InvestigationIntent` | `investigation_intent` | Reused enum | Existing intent values remain authoritative. |
| `InvestigationStateTransitionModel` / `services.investigation_state_machine.InvestigationState` | workflow-control fields | Adapted | Graph node/iteration counters complement rather than replace persistent transition history. |
| `investigation_state_machine.TERMINAL_STATES` | `terminal_status` | Adapted | `WorkflowTerminalStatus` adds API-neutral graph outcomes without changing existing API or database values. |
| `entity_resolution_service.EntityResolutionResult` | `entity_resolution_status` | Adapted | Adds deterministic `NOT_STARTED` and `FAILED` states while preserving resolved/ambiguous/not-found/blocked meanings. |
| `EntityCandidate`, `EntityResolution` | `entity_candidates`, `resolved_entities` | Adapted | Frozen validated records add database/schema and verified/inferred detail suitable for serialization. |
| `metadata_search_service.TableMetadata` and `object_ranking_agent.RankedObject` | object-discovery lists | Adapted | `DatabaseObjectRef` combines safe identity, relevance, dependency distance, disposition, and relationship verification. |
| Foreign-key metadata / inferred identifier matches | `relationship_edges` | New serialization shape | String object/column references represent normal and self-referencing edges without recursive object graphs. |
| `investigation_planner_agent` plan and `safe_investigation_planner.EvidenceRequest` | `investigation_plan` and step outcome lists | Adapted | `InvestigationPlanStep` stores objectives, dependencies, evidence goals, JOIN justification, validation, and status without a service reference. |
| `safe_sql_service.PlannedQuery` | proposed/approved/rejected query lists | Adapted | `QueryRecord` stores sanitized SQL or hash plus non-secret parameter metadata and validation outcome. |
| `evidence_execution_service.EvidenceResult` | `query_results`, evidence ID lists | Adapted | State retains execution metadata and evidence references, not large row sets. |
| `evidence_gap_detection_service.EvidenceGap` | `evidence_gaps`, `metadata_gaps` | Adapted | Adds affected entity/object, blocking flag, source node, and timestamp while retaining recommended-next-step semantics. |
| Reasoning claims and evidence references | `claim_evidence_links` | New reference shape | Keeps append-only evidence linkage without copying evidence bodies. |
| `EvidenceResult.evidence_semantics` | `findings` | Adapted | `EvidenceOutcome` distinguishes no row, NULL, required missing value, optional NULL, and missing relationship. |
| Ranked/selected objects and evidence results | coverage fields | New aggregate representation | Coverage is computed from required objects only; optional objects do not dilute or inflate it. |
| `evidence_gate_service.EvidenceGateResult.reproduced` | reproduction fields | Adapted | `WorkflowReproductionStatus` adds not-assessed/incomplete/blocked states instead of relying on a Boolean. |
| `reasoning_dispatch_service.ReasoningMode` | `reasoning_mode` | Adapted | Existing modes are preserved semantically; new pre-decision and human-review values support graph control before dispatch. |
| `ReasoningDispatchDecision` | reasoning-decision fields | Adapted | Represents permission, blockers, warnings, decision reason, and provider-call need; LG-03 implements no decision logic. |
| `reasoning_agent.ReasoningResult` | `reasoning_result` | Reference-ready dictionary | Allows no-LLM operation and future validated output without coupling state to a live provider. |
| `LLMInvocationAuditModel.id` | `llm_invocation_ids` | Reused reference | Preserves auditable provider-call references rather than embedding audit rows. |
| `report_generator.InvestigationReport` / report snapshot | reporting fields | Adapted | Supports a future structured payload and artifact IDs without generating reports. |
| `audit_service` error/status metadata | `errors`, `warnings` | Adapted | Frozen `ErrorRecord` values use existing secret masking and retain only sanitized context. |
| `InvestigationState.CANCELLED` and cancel endpoint | `cancel_requested`, `terminal_status` | Reused concept | Represents cancellation request and outcome without implementing cancellation behavior. |

## New controlled concepts

The following enums exist because no current enum covers the full pre-execution and graph-state
domain:

- `EntityResolutionStatus`
- `CoverageStatus`
- `WorkflowReproductionStatus`
- `WorkflowReasoningMode`
- `WorkflowTerminalStatus`
- `ObjectDisposition`
- `RelationshipVerification`
- `QueryValidationStatus`
- `QueryExecutionStatus`
- `EvidenceOutcome`

Existing `InvestigationIntent` is reused directly. The persistent
`investigation_state_machine.InvestigationState` remains the authoritative database transition
enum and is not modified.

## State invariants for future nodes

1. Nodes return only fields they update; they do not rebuild the whole state opportunistically.
2. Evidence references are append-only. `append_evidence_reference` suppresses only the duplicate
   ID and never removes unrelated references.
3. Once verified, an evidence reference cannot be silently downgraded to unverified.
4. Completed plan steps cannot silently return to pending.
5. Terminal status changes require an explicit permitted transition; ordinary partial updates
   must not overwrite a terminal result.
6. Iteration, planning, query, object, row, duration, rank, and dependency counters are validated
   as non-negative.
7. `calculate_coverage` uses required objects only. Optional objects never affect its denominator.
8. Raw credentials, tokens, API keys, secret parameter values, and full connection strings must
   never enter state.
9. Exceptions become `ErrorRecord` values; messages and context pass through the existing
   `sanitize_ai_trace` masking utility.
10. Large SQL result sets remain in evidence persistence. State stores evidence IDs and bounded
    execution metadata.

`InvestigationState` is a `TypedDict`. Nested records are frozen Pydantic models with
`extra="forbid"`. A Pydantic `TypeAdapter` performs JSON serialization and validation on
deserialization, including enum and timestamp reconstruction. Each factory call creates fresh
lists and dictionaries.
