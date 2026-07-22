# Azure Dev Demo Verification (2026-07-22)

## Environment
- Azure dev URL: https://ca-database-support-ai-dev.delightfulmoss-bad7d457.centralindia.azurecontainerapps.io/react
- Branch: feature/ui-cleanup-evaluation-delete-runs
- Commit: ba5ce4c4ab554bf3f0545c324ca32ab63e9be70f
- Deployment workflow: Deploy To Azure Container App
- GitHub Actions run: 29935439145
- Workflow result: success (completed 2026-07-22T15:57:12Z)

## Health
- Endpoint: https://ca-database-support-ai-dev.delightfulmoss-bad7d457.centralindia.azurecontainerapps.io/health
- Result: status=ok, components application=ok and connector_registry=ok

## Features Verified
- Evidence SQL readability: verified with populated, readable SQL blocks in SHP-5001 investigation.
- Executive RCA summary: verified on SHP-5001 investigation result.
- Evaluation dashboard redesign: verified updated layout, spacing, and controls.
- Run selection controls: verified Select All and Clear Selection interactions.
- Disposable non-protected deletion: verified deletion of pilot-smoke-v3 with refreshed run list.
- Feedback form and submission: verified form rendering and successful submission confirmation.
- Feedback failure state: verified error handling state (UI displayed Internal Server Error on invalid long payload case).
- Unauthorized feedback submission rejection: verified 403 response for read_only_user.

## Protection Policy Implemented
Backend enforcement now blocks deletion requests when any selected run is protected by:
- Metadata/flags: protected, official, frozen, release, published, final, protected_final_benchmark, imported_from_frozen_evidence, and related is_* flag variants.
- Case-insensitive name/suite tokens: protected, official, frozen, release, published, final, benchmark-125, all-125, rc-.
- API behavior: returns HTTP 403 with structured protected and missing details when blocked.

UI mirror behavior:
- Protected runs are non-selectable (disabled checkbox).
- Protected badge and tooltip reason displayed from server-provided protection reason.
- Run-management text reflects protected naming policy.

## Live Azure Protection Verification Status
- Current tenant run inventory after deployment: 2 runs, protected_count=0.
- Attempted to seed protected-pattern runs (rc-demo-protected-*): jobs were created but failed before producing persisted evaluation runs, so no protected run row became available for live blocked-delete click-through.
- Result: live protected blocked-deletion interaction could not be completed due data/runtime constraints.

## Disposable Run Deletion Evidence
- Deleted run: pilot-smoke-v3
- Confirm dialog text captured:
  - Delete 1 selected run?
  - - pilot-smoke-v3
  - Protected runs will be skipped.
- Post-delete API verification:
  - total_runs=2
  - run_names=[pilot-smoke-v4, azure-pilot-smoke-v2]
  - pilot_smoke_v3_exists=false

## Feedback Flow Result
- UI before-submit form: verified on investigation INV-20260715-132553-C0D249CB.
- Successful submission confirmation banner shown:
  - "Feedback submitted for approval. Dashboard counters and review queue have been refreshed."
- Persisted demo entry verified via API:
  - id: 51ec0498-054d-4b49-8540-70239162de29
  - investigation_id: INV-20260715-132553-C0D249CB
  - organization_id: 99e196a1-8d04-4b8f-8a5f-ca8f0bffbad2
  - workspace_id: 616ce141-5571-4af8-903e-9a377aa20888
  - status: PENDING_APPROVAL
  - notes includes: DEMO-FEEDBACK-20260722
- Unauthorized submission check:
  - read_only_user submit attempt returned HTTP 403.

## Restoration / Remediation Note (published-all-125-ai-judge)
What was deleted:
- Run name: published-all-125-ai-judge
- Scope: evaluation run and associated persisted run-linked artifacts/records removed by run deletion path.

Whether source artifacts still exist:
- Azure dev API currently shows no matching run rows and no matching evaluation job records for published/all-125 naming in current data.
- Repository/local artifacts exist for 125-related benchmark outputs (for example suite-full-125 JSON/ZIP artifacts), but these are not authoritative proof of exact Azure DB row state.

Impact:
- The specific dev run is no longer available in the evaluation dashboard list.
- Exact historical identity and row-linked metadata/report references are unavailable from current Azure API state.

Safe restoration options:
1. Preferred exact restore: recover Azure dev database from a snapshot/backup taken before deletion (transactionally restores run-linked rows and references).
2. If no backup exists: re-run benchmark flows to produce new evidence under a new run id/name; do not claim equivalence to the deleted run.
3. Optional archival import path: only if a signed immutable export with checksums and full relational mapping exists; otherwise do not reconstruct scores.

Recommendation:
- Do not fabricate or manually reconstruct benchmark scores.
- Treat exact restoration as not currently possible from available Azure API-visible records; use backup restore if required for exactness, else regenerate as a new run with explicit non-equivalence note.

## Screenshot Index
Folder: docs/demo/screenshots/azure-dev-20260722/

- application-dashboard-landing.png
- investigation-shp-5001-result.png
- investigation-evidence-sql-panel.png
- investigation-executive-rca-summary.png
- evaluation-dashboard-overview.png
- evaluation-run-selection-controls.png
- evaluation-select-all-state.png
- evaluation-deletion-success-refresh.png
- feedback-form-before-submission.png
- feedback-success-confirmation.png
- health-endpoint-ok.png
- protected-run-policy-state.png

## Remaining Limitations
- Live protected-run blocked-deletion screenshot for an actual protected row could not be produced because no protected runs were present and rc-pattern seed jobs failed before creating persisted run entries.
- Some UI interactions required Playwright-force click due transient overlay/pointer interception behavior in the deployed page.
