# Azure Smoke Test Checklist

Owner: Mukesh Dabi

Use this checklist after every Azure Container App deployment before freezing or demoing the build.

## 1. Confirm Container App Is Running

- Open Azure Portal.
- Go to resource group `rg-database-support-ai-dev`.
- Open Container App `ca-database-support-ai-dev`.
- Confirm latest revision is running and healthy.

Expected:

- Provisioning state: `Succeeded`
- Running status: `Running`
- Latest revision points to the latest GitHub commit image.

## 2. Health Endpoint

Open:

```text
https://ca-database-support-ai-dev.delightfulmoss-bad7d457.centralindia.azurecontainerapps.io/health
```

Expected:

- HTTP 200
- JSON response from FastAPI health endpoint

## 3. Login

Open:

```text
https://ca-database-support-ai-dev.delightfulmoss-bad7d457.centralindia.azurecontainerapps.io/app.html
```

Steps:

1. Login with an existing user.
2. Confirm dashboard loads.
3. Confirm workspace selector loads.

Expected:

- User logs in without needing to register again.
- Existing workspaces/documents are visible if the Azure PostgreSQL database was not recreated.

## 4. Database Connection

Steps:

1. Open Database Connections.
2. Select the active workspace.
3. Confirm the Azure MySQL/PostgreSQL target connection exists.
4. Click Test.

Expected:

- Connection test succeeds.
- No password or full connection string is exposed in the browser response.

## 5. Ask AI

Use a known seeded test question, for example:

```text
Appointment APT-2005 created two active lab orders.
Investigate like a Senior Production Support Engineer.
Identify affected object, parent object, write path, root cause, evidence, fix, tests, proof of fix, and rollback.
```

Expected:

- AI Chat shows concise summary cards.
- Full technical detail is collapsed.
- Report download buttons appear.
- The answer states AI-assisted reasoning enabled/disabled status.
- The report includes PII masking status.

## 6. Verification Checks

Steps:

1. Review Suggested Verification Checks.
2. Run one safe check.
3. Run all remaining safe checks.

Expected:

- SQL text is visible and editable before execution.
- Only read-only SQL runs.
- Results show in tabular format where possible.
- Verified report download buttons appear after checks run.

## 7. Report Downloads

Download:

- PDF
- Word
- Excel
- HTML report

Expected:

- Files download successfully.
- Report includes evidence, root cause, recommended fix, test cases, proof of fix, rollback, verification results, and AI/PII masking status.

## 8. Learning Loop

Steps:

1. Open Learning Loop.
2. Open the latest investigation.
3. Submit feedback.

Expected:

- Prior investigation can be opened.
- Feedback can be submitted for approval.
- Feedback does not become approved knowledge without review.

## 9. Audit Spot Check

If database access is available, verify recent audit events.

Expected audit actions:

- `USER_LOGIN`
- `INVESTIGATION_STARTED`
- `VERIFICATION_SQL_EXECUTED`
- `REPORT_DOWNLOADED`

## 10. Pass/Fail Decision

Pass when:

- Health endpoint works.
- Login works.
- Ask AI works.
- Verification checks run.
- Reports download.
- No secret leakage is visible.
- Latest revision matches the latest GitHub commit.

Fail when:

- App still runs an old image.
- Ask AI returns `Failed to fetch` or unsafe SQL errors for known valid questions.
- Reports are missing.
- Verification buttons do not work.
- Secrets appear in API responses.
