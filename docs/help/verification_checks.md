# Verification Checks

Suggested verification checks let a user approve read-only SQL that verifies claims in the report.

Navigation path: AI Chat -> Suggested Verification Checks -> Run this check or Run all safe checks.

Steps:
1. Run an investigation.
2. Scroll to Suggested Verification Checks.
3. Review the claim, SQL, expected result, risk, and source.
4. Click Run this check for one check.
5. Click Run all safe checks to run all pending safe checks.
6. Review the verification result table.
7. Download the verified report from the verification report buttons.

Warnings:
- Verification SQL must be SELECT, SHOW, DESCRIBE, DESC, or EXPLAIN.
- The app never executes INSERT, UPDATE, DELETE, ALTER, DROP, TRUNCATE, EXEC, or CALL for verification.
- Review SQL before running it.
