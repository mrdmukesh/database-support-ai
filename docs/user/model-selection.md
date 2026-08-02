# Selecting an investigation model

When enabled by an administrator, the investigation form shows only models authorized for your
role, workspace, environment, and user approvals.

- **Automatic** (recommended) deterministically chooses from your approved candidate set.
- **Fast** is intended for routine, lower-latency investigations.
- **Deep Analysis** is intended for complex multi-step reasoning and may require approval.

The labels describe intended use, speed and cost tier without exposing credentials or internal
deployment details. The server validates the selection again; changing the browser request cannot
grant access. If an administrator has explicitly enabled fallback, the result identifies the
effective model and fallback reason. Otherwise an unavailable or unauthorized selection is
rejected clearly.

Every model uses the same read-only SQL, evidence, safety and claim-verification controls. Saved
investigations show the model actually used even if it is later disabled.
