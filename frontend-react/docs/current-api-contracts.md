# Current frontend API contracts

Human-readable inventory of the contracts used by the legacy `app.html` frontend. This is documentation only; it does not define a new API or loosen backend authorization.

## Conventions

- The legacy frontend prefixes paths with `API_BASE`. On `localhost`/`127.0.0.1`, that defaults to `http://127.0.0.1:8001`; elsewhere it defaults to same-origin.
- Except for signup/login, system endpoints, and feature-flag-dependent organization bootstrap, requests use `Authorization: <token_type> <access_token>` (normally `Bearer <token>`).
- JSON requests use `Content-Type: application/json`. Document upload uses `multipart/form-data` and lets the browser set its boundary.
- Standard FastAPI validation failures are `422` with `{ "detail": ... }`. Auth failures are generally `401`; permission, tenant, or workspace denial is generally `403`; missing resources are generally `404`; uniqueness/conflict errors are generally `409`.
- The legacy `api()` helper clears its locally stored session on `401`, then throws a formatted `detail` message. It does not refresh tokens.
- **Uncertain** marks a route without a response model or a dictionary whose complete key set is not enforced by Pydantic.

## Shared response shapes

### Organization

`{ id, name, slug, is_active }`

### User

`{ id, organization_id, email, full_name, role, is_active }`

### Workspace

`{ id, organization_id, name, slug, is_active }`

### Database connection

`{ id, organization_id, workspace_id, engine, name, is_active }`. Secret references and connection strings are deliberately absent.

### Document

`{ id, organization_id, workspace_id, title, current_version }`

### Chat conversation

`{ id, organization_id, workspace_id, user_id, title }`

### Chat message

`{ id, conversation_id, role, content, confidence, source_count, requires_human_review }`; `confidence` is nullable.

### Verification check

`{ id, investigation_id, claim, purpose, claim_being_verified, evidence_logic, expected_result_explanation, interpretation, conclusion_template, verification_sql, expected_result, risk_level, source, status, actual_result_summary, confidence_impact, notes, verified_by, verified_at }`; `verified_at` is nullable. Several explanatory strings have empty-string defaults.

### Investigation summary

`{ id, organization_id, workspace_id, user_question, detected_intent, ai_answer, confidence_score, report_path, status, created_at }`; `confidence_score` is nullable on list/dashboard responses.

### Feedback

`{ id, organization_id, workspace_id, investigation_id, rating, actual_root_cause, actual_fix_applied, sql_or_procedure_changed, test_cases_executed, proof_of_fix, rollback_used, production_issue_resolved, notes, status, review_notes, created_at }`; `production_issue_resolved` is nullable.

### Knowledge article

`{ id, workspace_id, title, module_name, issue_type, symptoms, actual_root_cause, fix_summary, test_cases, proof_of_fix, severity, confidence_after_approval, source_investigation_id, version, is_active, approved_at }`; the confidence, source investigation, and approval timestamp are nullable.

## Authentication, signup, and session

### Create organization

- **Method/URL:** `POST /organizations`
- **Request:** `{ name, slug }`; slug must be lowercase alphanumeric/hyphen and start alphanumeric.
- **Response:** Organization; `201`.
- **Optional fields:** none.
- **Errors:** `409` organization exists; `401`/`403` under enterprise RBAC; `422` validation.
- **Authentication:** feature-dependent. With enterprise RBAC enabled, super-admin authentication is required. Legacy signup attempts this before a user session exists, so successful self-service bootstrap depends on current feature configuration.
- **Legacy use:** signup form creates or looks up the organization (`app.html`, signup submit handler).

### List organizations

- **Method/URL:** `GET /organizations`
- **Request:** none.
- **Response:** Organization array.
- **Optional fields:** none.
- **Errors:** `401` invalid/missing auth when enterprise RBAC is enabled.
- **Authentication:** feature-dependent; non-super-admin users are tenant-filtered.
- **Legacy use:** fallback lookup by slug when create reports an existing organization.

### Signup

- **Method/URL:** `POST /auth/signup`
- **Request:** `{ organization_id, email, password, full_name, role, consents, ip_address }`.
- **Optional/default fields:** `full_name` defaults `""`; `role` defaults `read_only`. The legacy UI supplies both. `consents` and `ip_address` are required.
- **Response:** User; `201`. Password and consent details are not returned.
- **Errors:** `422` weak password, invalid email, or missing required consent; `409` user exists/invalid organization.
- **Authentication:** none at route level.
- **Legacy use:** signup flow after organization creation.

### Login

- **Method/URL:** `POST /auth/login`
- **Request:** `{ email, password }`.
- **Response:** `{ access_token, token_type, user }`; `token_type` defaults to `bearer`.
- **Optional fields:** none in the actual response.
- **Errors:** `401 { detail: "Invalid credentials" }`; `422` validation.
- **Authentication:** none.
- **Legacy use:** login form and post-signup automatic login.

### Browser session handling

- **Endpoint:** none.
- **Storage:** the full login response is stored in `localStorage` under `legacydb-session`.
- **Use:** authorization header creation, role checks, tenant/user IDs, logout.
- **Expiry behavior:** any JSON API `401` removes local storage and propagates the API error. Report/document fetches use separate fetch logic and do not consistently clear the stored session.
- **Uncertain:** no refresh-token, logout, session-introspection, or server-side revocation endpoint is used by the legacy frontend.

## System and dashboard

### Health

- **Method/URL:** `GET /health`
- **Request:** none.
- **Response:** `{ status, components }`, where each component is `{ name, status, detail }`.
- **Optional fields:** not declared by a Pydantic response model; component detail may vary. **Uncertain.**
- **Errors:** generic server errors.
- **Authentication:** none.
- **Legacy use:** API status indicator.

### AI disclaimer

- **Method/URL:** `GET /ai/disclaimer`
- **Request:** none.
- **Response:** `{ disclaimer: string[] }`.
- **Optional fields:** none.
- **Errors:** generic server errors.
- **Authentication:** none.
- **Legacy use:** dashboard disclaimer list.

### Admin summary

- **Method/URL:** `GET /admin/summary`
- **Request:** none.
- **Response:** `{ organizations, users, active_subscriptions, documents, incidents }`, all integer counts.
- **Optional fields:** none in implementation, but route has no response model. **Uncertain only as to future extra keys.**
- **Errors:** `401` unauthenticated; `403` missing `admin:read`.
- **Authentication:** bearer token with `admin:read`; results are tenant-filtered unless super-admin.
- **Legacy use:** dashboard count cards (the legacy UI currently displays all except `active_subscriptions`).

## Workspaces

### List workspaces

- **Method/URL:** `GET /workspaces?organization_id={organization_id}`
- **Request:** required query `organization_id`.
- **Response:** Workspace array.
- **Optional fields:** none.
- **Errors:** `401`, `403` tenant/permission failure, `422` missing query.
- **Authentication:** `workspaces:read`; enterprise users may be membership-filtered.
- **Legacy use:** dashboard, workspace manager, connection/document/chat/learning selectors.

### Create workspace

- **Method/URL:** `POST /workspaces`
- **Request:** `{ organization_id, name, slug }`.
- **Response:** Workspace; `201`.
- **Optional fields:** none.
- **Errors:** `409` duplicate/invalid organization; `401`/`403`; `422` validation.
- **Authentication:** `workspaces:manage`, same organization. Creator receives owner membership.
- **Legacy use:** default workspace creation during signup and workspace form.

### Update workspace

- **Method/URL:** `PATCH /workspaces/{workspace_id}`
- **Request:** any subset of `{ name, slug, is_active }`.
- **Response:** Workspace.
- **Optional fields:** all request fields optional.
- **Errors:** `404` not found; `409` update conflict; `401`/`403`; `422`.
- **Authentication:** `workspaces:manage` plus workspace admin access.
- **Legacy use:** workspace edit action; currently sends `{ name }`.

### Delete workspace

- **Method/URL:** `DELETE /workspaces/{workspace_id}`
- **Request:** path ID only.
- **Response:** `204`, no body. This is a soft deactivation.
- **Optional fields:** none.
- **Errors:** `404`; `401`/`403`.
- **Authentication:** `workspaces:manage` plus workspace admin access.
- **Legacy use:** workspace delete action.

## Database connections and validation

### List connections

- **Method/URL:** `GET /databases/connections?organization_id={organization_id}`; optional `workspace_id` is supported but not sent by the legacy manager.
- **Request:** required `organization_id`; optional `workspace_id`.
- **Response:** Database connection array.
- **Errors:** `401`/`403`; `422` missing organization.
- **Authentication:** bearer token; same organization and, when workspace-filtered, workspace read access.
- **Legacy use:** connection table.

### Create connection

- **Method/URL:** `POST /databases/connections`
- **Request:** `{ organization_id, workspace_id, engine, name, host, port, database_name, secret_ref, connection_string }`.
- **Optional/default fields:** `host`, `database_name`, `secret_ref` default empty; `port` and `connection_string` are nullable. Either usable `secret_ref` or `connection_string` is required by service logic.
- **Response:** Database connection; `201`; secrets are omitted.
- **Errors:** `422` invalid/missing secret reference or connection string; `409` persistence conflict; `401`/`403`.
- **Authentication:** authenticated same-organization user with workspace database access.
- **Legacy use:** connection form.

### Update connection

- **Method/URL:** `PATCH /databases/connections/{connection_id}`
- **Request:** any subset of `{ name, connection_string, is_active }`.
- **Response:** Database connection.
- **Optional fields:** all request fields optional.
- **Errors:** `404 { detail: "Connection not found" }`; `409`; `401`/`403`; `422`.
- **Authentication:** bearer token with database access to owning workspace.
- **Legacy use:** edit action currently sends `{ name }`.

### Delete connection

- **Method/URL:** `DELETE /databases/connections/{connection_id}`
- **Request:** path ID only.
- **Response:** `204`, no body; soft deactivation.
- **Errors:** `404`; `401`/`403`.
- **Authentication:** database access to owning workspace.
- **Legacy use:** delete action.

### Test connection

- **Method/URL:** `POST /databases/connections/{connection_id}/test`
- **Request:** no body.
- **Response:** `{ connection_id, is_valid, message }`.
- **Optional fields:** none in implementation; no response model. **Uncertain only as to future extra keys.**
- **Errors:** `404`; `401`/`403`. A connector failure normally returns HTTP `200` with `is_valid: false`, not an HTTP error.
- **Authentication:** database access to owning workspace.
- **Legacy use:** Test button and inline result cell.

## Documents

### List documents

- **Method/URL:** `GET /documents?organization_id={organization_id}`; optional `workspace_id` is supported but not sent by the legacy manager.
- **Request:** required `organization_id`; optional `workspace_id`.
- **Response:** Document array.
- **Errors:** `401`/`403`; `422` missing organization.
- **Authentication:** bearer token, same organization; workspace filter adds workspace read enforcement.
- **Legacy use:** document table and workspace-name lookup.

### Upload document

- **Method/URL:** `POST /documents/upload`
- **Request:** multipart fields `organization_id`, `workspace_id`, `title`, and binary `file`.
- **Response:** Document; `201`.
- **Optional fields:** none.
- **Errors:** `422` file type/size/policy or form validation; `409` persistence conflict; `401`/`403`.
- **Authentication:** bearer token, same organization, workspace upload access.
- **Legacy use:** upload form uses direct `fetch` so it does not set JSON content type.

## Investigation submission and conversations

### Submit investigation

- **Method/URL:** `POST /chat/ask`
- **Request:** `{ organization_id, workspace_id, user_id, question, conversation_id? }`; question length 1–4000.
- **Response:** `{ conversation, user_message, assistant_message, findings, confidence, requires_human_review, sources, report, investigation_id }`.
- **Optional fields:** `conversation_id` request is nullable; `report` and `investigation_id` response are nullable. Message `confidence` is nullable.
- **Report dictionary:** when generated, observed keys include `investigation_id`, `mode`, `html`, `pdf`, `docx`, `xlsx`, `audit_html`, `audit_pdf`, `audit_docx`, `audit_xlsx`, and optionally `ai_trace`. The schema only guarantees `dict[str, str]`, so key presence is **uncertain** and callers must tolerate omissions.
- **Errors:** `401`/`403` auth, tenant, user, or workspace denial; `422` prompt/request validation; investigation/report failures may surface as route-generated HTTP errors with `detail`.
- **Authentication:** `chat:use`, same organization/user, workspace investigate access.
- **Legacy use:** AI Chat form; renders assistant content, badges, report actions, feedback, checks, and history.

### List conversations

- **Method/URL:** `GET /chat/conversations?organization_id={organization_id}&workspace_id={workspace_id}&user_id={user_id}`
- **Request:** three required query fields.
- **Response:** Chat conversation array.
- **Optional fields:** none.
- **Errors:** `401`/`403`; `422` missing query.
- **Authentication:** `chat:use`, same organization/user, workspace read access.
- **Legacy use:** chat-history buttons.

### List conversation messages

- **Method/URL:** `GET /chat/conversations/{conversation_id}/messages?organization_id={organization_id}&workspace_id={workspace_id}&user_id={user_id}`
- **Request:** path conversation ID plus three required query fields.
- **Response:** Chat message array.
- **Optional fields:** message confidence nullable.
- **Errors:** `404` conversation not found; `401`/`403`; `422`.
- **Authentication:** `chat:use`, same organization/user, workspace read access, conversation ownership checks.
- **Legacy use:** conversation selection and last-assistant answer restoration.

## Investigation history

### Learning investigation list

- **Method/URL:** `GET /learning/investigations?organization_id={organization_id}&workspace_id={workspace_id}`; optional `status_filter` supported.
- **Request:** required organization/workspace query; optional status filter.
- **Response:** Investigation summary array, maximum 100.
- **Errors:** `401`/`403`; `422`.
- **Authentication:** `learning:read`, same organization, workspace read.
- **Legacy use:** learning-loop open investigation table.

### Get saved investigation

- **Method/URL:** `GET /learning/investigations/{investigation_id}`
- **Request:** path ID.
- **Response:** `{ id, organization_id, workspace_id, user_question, detected_intent, ai_answer, confidence_score, report_path, status, created_at, report }`.
- **Optional/uncertain fields:** route has no response model. `confidence_score` is forced to a number (`0` fallback). `report` currently contains `{ investigation_id, html, pdf, docx, xlsx }`; its exact shape is **uncertain**.
- **Errors:** `404 { detail: "Investigation not found" }`; `401`/`403`.
- **Authentication:** `learning:read` and owning workspace read access.
- **Legacy use:** reopens saved result in Chat, restores badges/reports/feedback/checks.

## Reports

### Download/view report artifact

- **Method/URL:** `GET /reports/{investigation_id}/{filename}`
- **Request:** path IDs only; legacy uses URLs returned in `report` dictionaries.
- **Response:** binary/file response. Allowed extensions: `.html`, `.pdf`, `.docx`, `.xlsx`. HTML/PDF are inline; DOCX/XLSX are attachments.
- **Optional fields:** not JSON.
- **Errors:** `404 { detail: "Report file not found" }`; `401`/`403` workspace/auth denial.
- **Authentication:** `chat:use`, owning workspace read access.
- **Legacy use:** HTML viewer and PDF/Word/Excel download buttons.

### Download AI debug trace

- **Method/URL:** `GET /reports/{investigation_id}/ai-debug-trace`
- **Request:** path ID.
- **Response:** downloadable JSON `{ investigation_id, trace }`; `trace` is sanitized and dynamically shaped. **Uncertain.**
- **Optional fields:** the entire endpoint is feature/environment-dependent.
- **Errors:** `404` disabled, missing investigation, or missing trace; `403` non-admin; `401` unauthenticated/workspace denial.
- **Authentication:** `admin:read`, super-admin or organization-admin, workspace read. Disabled in production and unless debug trace is enabled.
- **Legacy use:** conditionally rendered for `super_admin`, `organization_admin`, or `dba`; note that backend authorization is stricter than the legacy visibility check, so DBA requests can receive `403`.

## Verification checks

### List checks

- **Method/URL:** `GET /chat/investigations/{investigation_id}/verification-checks`
- **Request:** path ID.
- **Response:** Verification check array.
- **Errors:** `404` investigation; `401`/`403`.
- **Authentication:** `chat:use`, owning workspace read.
- **Legacy use:** verification panel after generation/reopening.

### Run one check

- **Method/URL:** `POST /chat/verification-checks/{check_id}/run`
- **Request:** `{ verification_sql }`; nullable/optional, with stored SQL used when omitted.
- **Response:** Verification check.
- **Errors:** `404` check/investigation/connection; `409` non-pending state where applicable; `422` unsafe/invalid SQL; `401`/`403`.
- **Authentication:** `chat:use`, owning workspace verification/database access.
- **Legacy use:** editable safe-SQL Run button.

### Skip one check

- **Method/URL:** `POST /chat/verification-checks/{check_id}/skip`
- **Request:** no body.
- **Response:** Verification check.
- **Errors:** `404`; `409` state conflict where applicable; `401`/`403`.
- **Authentication:** `chat:use`, owning workspace access.
- **Legacy use:** Skip button.

### Run all pending checks

- **Method/URL:** `POST /chat/investigations/{investigation_id}/verification-checks/run-all`
- **Request:** no body.
- **Response:** `{ checks, report }`; `report` is nullable and dynamically keyed as described under investigation submission.
- **Errors:** `404`; `422` verification execution/safety errors; `401`/`403`.
- **Authentication:** `chat:use`, owning workspace access.
- **Legacy use:** Run All button; refreshes check cards and regenerated report links.

## Feedback and learning loop

### Learning dashboard

- **Method/URL:** `GET /learning/dashboard?organization_id={organization_id}&workspace_id={workspace_id}`
- **Request:** required organization/workspace query.
- **Response:** `{ open_investigations, pending_feedback, pending_approval, approved_knowledge, reminders }`; reminders are Investigation summaries.
- **Errors:** `401`/`403`; `422`.
- **Authentication:** `learning:read`, same organization/workspace.
- **Legacy use:** learning count cards and reminder table.

### Submit investigation feedback

- **Method/URL:** `POST /learning/investigations/{investigation_id}/feedback`
- **Request:** `{ rating, actual_root_cause, actual_fix_applied, sql_or_procedure_changed, test_cases_executed, proof_of_fix, rollback_used, production_issue_resolved, notes }`.
- **Optional/default fields:** all text fields default empty; `production_issue_resolved` is nullable. `rating` is required and must be one of `HELPFUL`, `NOT_HELPFUL`, `PARTIALLY_CORRECT`, `WRONG_ROOT_CAUSE`, `MISSING_EVIDENCE`, `NEEDS_DBA_REVIEW`.
- **Response:** Feedback; `201`, normally status `PENDING_APPROVAL`.
- **Errors:** `404`; `401`/`403`; `422` invalid rating/payload.
- **Authentication:** `learning:feedback`, owning workspace write.
- **Legacy use:** feedback panel below an investigation.

### List feedback

- **Method/URL:** `GET /learning/feedback?organization_id={organization_id}&workspace_id={workspace_id}&status_filter=PENDING_APPROVAL`
- **Request:** required organization/workspace; optional status filter.
- **Response:** Feedback array, maximum 100.
- **Errors:** `401`/`403`; `422`.
- **Authentication:** `learning:read`, same organization/workspace.
- **Legacy use:** pending approval table.

### Review feedback

- **Method/URL:** `POST /learning/feedback/{feedback_id}/review`
- **Request:** `{ approved, review_notes, title, module_name, issue_type, severity, rollback_plan, confidence_after_approval }`.
- **Optional/default fields:** `title` nullable; other descriptive fields default empty; severity defaults `medium`; confidence defaults `0.95` and must be 0–1. Legacy sends only `approved`, nullable `title`, `review_notes`, and confidence.
- **Response:** updated Feedback. Approval may also create knowledge, but that article is not returned.
- **Errors:** `404 { detail: "Feedback not found" }`; `401`/`403`; `422`.
- **Authentication:** `learning:approve`, owning workspace approve access.
- **Legacy use:** Approve/Reject actions.

### List approved knowledge

- **Method/URL:** `GET /learning/knowledge?organization_id={organization_id}&workspace_id={workspace_id}`
- **Request:** required organization/workspace query.
- **Response:** active Knowledge article array, maximum 100.
- **Errors:** `401`/`403`; `422`.
- **Authentication:** `learning:read`, same organization/workspace.
- **Legacy use:** approved knowledge table.

## Legacy error handling notes

- JSON errors are normalized from FastAPI `detail`, including arrays of validation errors.
- A `401` from the generic JSON helper clears `legacydb-session`; it does not automatically navigate to login.
- Document upload and report downloads use direct `fetch` paths with separate error parsing and therefore do not share all generic session/error behavior.
- Connection-test failures are represented as successful HTTP responses with `is_valid: false`.
- Several UI flows recover from specific English error text (`"already"`, `"exists"`), which is a fragile legacy coupling and should be preserved until the React migration has explicit typed handling.

## Source locations

- Legacy usage: `app.html`
- Request/response schemas: `src/legacydb_copilot/schemas.py`
- Routes: `src/legacydb_copilot/routers/`
- Report-link generation: `src/legacydb_copilot/services/report_generator.py` and `src/legacydb_copilot/routers/learning.py`
