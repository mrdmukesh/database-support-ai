# Cleanup Dependency Report

Date: 2026-08-04

## 1. Executive Summary

- **Scope of cleanup:** In-application destructive cleanup for test application data scoped to a single `organization_id`. The endpoint is `POST /admin/test-data-cleanup/execute` and supports a dry-run preview endpoint `POST /admin/test-data-cleanup/preview`.
- **Objects preserved:** Users (including administrators), authentication records, application configuration, persistent application databases, and external/physical target databases/infrastructure. The endpoint explicitly blanks in-DB `secret_ref` values for `DatabaseConnectionModel` instead of deleting external secrets or dropping physical DBs.
- **Objects deleted:** Investigation-related artifacts (investigations, execution traces, agentic steps, planner selections, feedback, verification checks), database connections (after blanking `secret_ref`), workspace memberships and workspaces, and associated report/metadata where present. LLM invocation audit entries are explicitly deleted by the cleanup flow because they are not universally FK-linked.
- **Physical databases:** Explicit confirmation: this cleanup endpoint does NOT delete physical target databases; `physical_databases_deleted` in the endpoint summary is always `0` and the code blanks `secret_ref` instead of issuing external deletion.

## 2. Complete Dependency Graph (high-level)

This section lists the major logical areas and the primary tables involved in the cleanup (ordered by conceptual dependency groups):

- Workspaces (`WorkspaceModel`)
- Workspace memberships (`WorkspaceMembershipModel`)
- Database connections (`DatabaseConnectionModel`) — stores `secret_ref` and workspace/organization mapping
- Investigations (`InvestigationModel`) — owner of many investigation-level artifacts
- Evidence / Documents (`DocumentModel`)
- Execution traces (`ExecutionPathTraceModel`)
- Planner selections (`InvestigationPlannerSelectionModel`)
- Agentic steps (`InvestigationAgenticStepModel`)
- LLM invocation audit (`LLMInvocationAuditModel`)
- Feedback (`InvestigationFeedbackModel`)
- Verification checks (`VerificationCheckModel`)
- Audit logs / metadata (`AuditLogModel`)
- Reports and persisted investigation artifacts (report paths stored on `InvestigationModel`)

Note: The codebase contains additional ancillary tables (subscriptions, incidents, knowledge-articles, etc.) that are not in-scope for the immediate cleanup but are referenced below where relevant.

## 3. Foreign Key Analysis

The following entries summarize parent→child relationships that are relevant to the cleanup. Where possible the analysis notes the actual FK behavior observed in Alembic/metadata or flagged during introspection. If a relationship was verified by Alembic or metadata introspection it is indicated; otherwise the ORM mapping is noted.

- Parent: `workspaces` (`WorkspaceModel`)
  - Child: `database_connections` (`DatabaseConnectionModel`) — FK column: `workspace_id`
  - ON DELETE behavior: migrations/metadata show many workspace-related FKs use `ON DELETE CASCADE` for child rows. `passive_deletes=True` is set on `WorkspaceModel.database_connections` so ORM will not issue explicit deletes when the workspace row is removed.
  - ORM relationship: `WorkspaceModel.database_connections` with `passive_deletes=True`.
  - Cleanup reliance: Database cascade (DB-level) where `ON DELETE CASCADE` exists; otherwise the cleanup explicitly deletes `DatabaseConnectionModel` rows via ORM after blanking `secret_ref`.

- Parent: `workspaces`
  - Child: `documents` (`DocumentModel`) — FK column: `workspace_id` and `owner_id` references `users`.
  - ON DELETE behavior: verified as cascade for workspace->documents in Alembic in most revisions; ORM `WorkspaceModel.documents` uses `passive_deletes=True`.
  - Cleanup reliance: DB cascade expected; the cleanup code removes workspaces which triggers DB cascades where present.

- Parent: `workspaces`
  - Child: `investigations` (`InvestigationModel`) — FK column: `workspace_id` (and `organization_id`)
  - ON DELETE behavior: migrations include `ondelete="CASCADE"` for many investigation-related FK constraints.
  - ORM relationship: `WorkspaceModel.investigations` with `passive_deletes=True`.
  - Cleanup reliance: DB cascade where present; explicit ORM deletes of `InvestigationModel` are also performed in the cleanup to ensure deterministic ordering.

- Parent: `investigations` (`InvestigationModel`)
  - Child: `execution_path_traces` (`ExecutionPathTraceModel`) — FK: `investigation_id`
  - Child: `investigation_agentic_steps` (`InvestigationAgenticStepModel`) — FK: `investigation_id`
  - Child: `investigation_planner_selections` (`InvestigationPlannerSelectionModel`) — FK: `investigation_id`
  - Child: `investigation_feedback` (`InvestigationFeedbackModel`) — FK: `investigation_id`
  - Child: `verification_checks` (`VerificationCheckModel`) — FK: `investigation_id`
  - Child: (some) audit/knowledge artifacts — e.g., `knowledge_articles.source_investigation_id` is nullable and in migrations was observed to `SET NULL` instead of `CASCADE`.
  - ON DELETE behavior: many child FKs are `ON DELETE CASCADE`; some optional pointers use `SET NULL` (intentional for historical records).
  - ORM relationship: `InvestigationModel` defines cascades in several child relationships (some use `cascade="all, delete-orphan"` depending on model).
  - Cleanup reliance: Mixed — cleanup explicitly deletes verification, feedback, traces, agentic steps, planner selections (in that order) and then deletes investigations; DB cascade provides redundancy for other child tables.

- Parent: `investigations` / organization
  - Child: `llm_invocation_audit` (`LLMInvocationAuditModel`) — NOTE: historically these records sometimes lack a direct FK to investigations (or are loosely linked) depending on version.
  - ON DELETE behavior: Not consistently FK-constrained across schema variations; in the current code path the cleanup explicitly deletes `LLMInvocationAuditModel` rows (to avoid orphan retention).
  - ORM relationship: `LLMInvocationAuditModel` exists as a model; it may or may not have a strict FK to `investigations` depending on migrations.
  - Cleanup reliance: Explicit ORM delete (implemented in `execute_test_data_cleanup`) — necessary because DB cascade cannot be relied on for these rows in all migrations.

- Parent: `database_connections` (`DatabaseConnectionModel`)
  - Child relationships: stored-credential references / external secret pointers (in `secret_ref`) — these are not externalized in the DB as FKs; the cleanup blanks `secret_ref` rather than deleting an external secret.
  - ON DELETE behavior: many DB-level FKs referencing `database_connections.id` exist and are generally `ON DELETE CASCADE` where appropriate.
  - Cleanup reliance: ORM update to blank secret_ref, then ORM delete of `DatabaseConnectionModel` rows (code uses `.update()` then `.delete()`).

- Parent: `users` / `administrators`
  - Child: document `owner_id`, membership rows, etc.
  - ON DELETE behavior: Users are intentionally preserved; cleanup does not delete `UserModel` rows.
  - Cleanup reliance: The code prevents user deletions by design — any child rows referencing users are removed via investigation/workspace cascades while users remain.

- Parent: `audit_logs` (`AuditLogModel`)
  - FK: `workspace_id` often exists and is nullable in some migrations; Alembic shows some `SET NULL` semantics for audit-related pointers.
  - Cleanup reliance: Audits are preserved (the cleanup records start/final audit events and does not purge audit logs). Where audit FK is nullable the DB will `SET NULL` when workspaces are removed.

Notes on verification sources: the above mapping is derived from ORM models, the Alembic/versions history, and introspection runs performed while implementing `passive_deletes=True`. Specific FK behaviors were confirmed for the most common investigation/workspace FKs (many show `ondelete="CASCADE"`).

## 4. Cleanup Order (exact sequence from `execute_test_data_cleanup`)

The endpoint deletes rows in the following FK-safe order (ORM calls seen in `src/legacydb_copilot/routers/admin.py`):

1. `VerificationCheckModel` (verification_and_root_cause)
2. `InvestigationFeedbackModel` (feedback)
3. `ExecutionPathTraceModel` (execution_traces)
4. `InvestigationAgenticStepModel` (agentic_steps)
5. `InvestigationPlannerSelectionModel` (planner_selections)
6. `LLMInvocationAuditModel` (llm_invocation_audit) — explicit delete because a dependable FK was not present across versions
7. `InvestigationModel` (investigations)
8. Update `DatabaseConnectionModel.secret_ref` to empty string
9. Delete `DatabaseConnectionModel` rows (database_connections)
10. `WorkspaceMembershipModel` rows (workspace_memberships)
11. `WorkspaceModel` rows (workspaces)

The endpoint then optionally re-creates a default workspace and membership when `keep_default_workspace` is requested and the organization ends up with zero workspaces.

## 5. Tables Preserved (explicit)

- `UserModel` (all users preserved)
- `OrganizationModel` (organization records preserved)
- Authentication tables (sessions/tokens/password hashes) — preserved
- Application configuration / settings tables — preserved
- Persistent application database records not scoped to the organization cleanup (e.g., central license/subscription rows) — preserved
- Physical target databases and external secrets — not deleted; `secret_ref` values are blanked but external deletion is out of scope
- Azure or other cloud infra resources — not deleted by this endpoint

## 6. Test Coverage (cleanup-related tests)

- `tests/test_admin_cleanup.py` — unit-level tests for the preview and execute endpoints, confirmation guard, environment guard, and summary values (dry-run and execute behavior).
- `tests/test_admin_cleanup_more.py` — additional unit/regression tests for edge cases in admin cleanup.
- `tests/test_orm_cascade_flags.py` — asserts that `WorkspaceModel` relationships include `passive_deletes=True` where DB cascade is used.
- `tests/test_cleanup_integration.py` — an integration test that:
  - builds a realistic record graph (organization, workspace, database connection, investigation and all related child rows),
  - enables SQLite PRAGMA foreign_keys=ON for DB-level cascade semantics,
  - runs the cleanup endpoint,
  - verifies via direct DB queries that all affected child tables (connections, investigations, documents, traces, agentic steps, planner selections, feedback, verification checks, LLM audit) have zero rows for the organization,
  - asserts `physical_databases_deleted == 0`, that users are preserved and administrator account exists, and that a second run of cleanup is idempotent.

Test notes: These tests were iteratively adjusted to ensure required non-null fields (e.g., `created_by_id`, `owner_id`, `logical_request_id`) are present when building objects via direct DB session usage.

## 7. Remaining Risks

- `LLMInvocationAuditModel`: historically inconsistent FK linkage means DB cascade cannot be relied on; the code now explicitly deletes these rows. Risk: future schema changes could reintroduce variations; keep explicit delete or add a FK + ON DELETE CASCADE migration.
- `AuditLogModel` and other metadata tables: many audit and knowledge artifacts intentionally use `SET NULL` for historical traceability. If these columns are non-nullable in older migrations, workspace deletion could fail — however current migrations observed use `SET NULL` for `audit_logs.workspace_id`.
- Incomplete migration coverage: `passive_deletes=True` was added to some `WorkspaceModel` relationships. This is safe only when the corresponding DB FK includes `ON DELETE CASCADE`. Any mismatch (passive_deletes=True but FK lacks cascade) could leave orphaned child rows or cause the ORM to issue deletes unexpectedly. A small set of FKs require migration updates (see Recommendations).
- PostgreSQL vs SQLite behavior: unit/integration tests run against SQLite with PRAGMA `foreign_keys=ON`. Postgres semantics are compatible for `ON DELETE` behaviors, but a PostgreSQL integration test is recommended before production rollout.

## 8. Recommendations

1. Migration changes where missing:
   - For every `WorkspaceModel` relationship that sets `passive_deletes=True`, ensure the DB FK is created or migrated to include `ON DELETE CASCADE`.
   - Example Alembic alter (pseudo):

```python
op.drop_constraint('fk_child_workspace_id', 'child_table', type_='foreignkey')
op.create_foreign_key('fk_child_workspace_id', 'child_table', 'workspaces', ['workspace_id'], ['id'], ondelete='CASCADE')
```

2. LLM invocation audit:
   - Either keep the explicit ORM delete (current code) or add a strict FK from `llm_invocation_audit.investigation_id` → `investigations.id` with `ON DELETE CASCADE` in a targeted migration.

3. Tests and CI:
   - Add a lightweight PostgreSQL integration job that runs `tests/test_cleanup_integration.py` against a Postgres test DB (containerized) to validate real PG FK semantics and `passive_deletes` assumptions.
   - Keep the SQLite integration test (fast, runs on dev machines) but run Postgres checks in CI.

4. Audit and retention policy:
   - Audit logs are preserved; if a future policy requires audit purging, implement a dedicated retention job that respects regulatory requirements.

5. Documentation for frontend team:
   - The frontend `Reset Test Application Data` page must require the exact confirmation string: `DELETE TEST APP DATA` and only enable the action when the environment variable `ALLOW_TEST_DATA_CLEANUP` is present and true in the environment the backend runs in (the endpoint checks `ALLOW_TEST_DATA_CLEANUP` in env).

## 9. Final Readiness

- Status: The backend cleanup endpoint is functionally implemented and covered by both unit and integration tests demonstrating: (a) deletion of investigation-scoped artifacts, (b) blanking of `secret_ref` values instead of external secret deletion, (c) preservation of users and admin accounts, and (d) idempotency on repeated runs.
- Caveats before full frontend rollout:
  - Add PostgreSQL integration test coverage in CI to validate `passive_deletes`/`ON DELETE CASCADE` assumptions against the production engine.
  - Reconcile any remaining `passive_deletes=True` cases that lack `ON DELETE CASCADE` in migrations (small migration additions recommended above).

Conclusion: Ready for the frontend `Reset Test Application Data` page behind the documented guard (confirmation string + environment variable) provided the two recommendations (Postgres CI integration and a short migration run to fix any missing ON DELETE CASCADE FKs) are completed as high priority follow-ups.

---

Files referenced during this analysis:

- [src/legacydb_copilot/routers/admin.py](src/legacydb_copilot/routers/admin.py#L1-L400)
- `src/legacydb_copilot/db/models.py` (workspace and investigation relationships were updated to `passive_deletes=True` during implementation)
- Integration test: [tests/test_cleanup_integration.py](tests/test_cleanup_integration.py#L1-L200)

If you want, I can now run an automated introspection pass that enumerates every FK row-by-row into a CSV for exact migration patches, or I'll proceed to mark this task done and wait for your review.
