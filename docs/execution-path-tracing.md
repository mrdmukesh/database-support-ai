# Execution Path Tracing (AG-06)

The deterministic tracing service reconstructs an expected processing path for a resolved
entity from supplied evidence observations. It does not execute SQL and does not infer that
an object executed merely because its definition or dependency was discovered.

## Verification labels

- `RUNTIME_VERIFIED`: workflow, job, exception, or equivalent runtime evidence proves the
  step occurred.
- `DATA_STATE_VERIFIED`: persisted entity or status-history state proves the step.
- `METADATA_ONLY`: a procedure, trigger, function, job, or dependency exists, but execution
  is not proven.
- `INFERRED_BUT_UNVERIFIED`: the path suggests the step, without independent proof.
- `MISSING`: no evidence exists for an expected step.
- `CONTRADICTORY`: states or timestamps cannot both be true in the expected order.

The trace reports the expected path, all verified completed steps, last verified successful
step, first failed/missing/inconsistent step, supported responsible component, and the
remaining gap. Every node and edge retains its evidence references.

The persisted trace is available at:

```text
GET /investigations/{investigation_id}/execution-path
```

## Payroll sample

```json
{
  "affected_entity": "EMP-1001",
  "expected_path": ["employee_ready", "payroll_calculation", "payroll_item_created"],
  "verified_completed_steps": ["employee_ready"],
  "last_successful_step": "employee_ready",
  "first_failed_or_missing_step": "payroll_calculation",
  "responsible_component": "",
  "remaining_gap": "Runtime execution proof is missing for Payroll Calculation.",
  "nodes": [
    {
      "step_id": "employee_ready",
      "verification_label": "DATA_STATE_VERIFIED",
      "outcome": "COMPLETED",
      "evidence_refs": ["SQL-EMPLOYEE"]
    },
    {
      "step_id": "payroll_calculation",
      "verification_label": "METADATA_ONLY",
      "outcome": "UNVERIFIED",
      "evidence_refs": ["PROC-CALCULATE"]
    },
    {
      "step_id": "payroll_item_created",
      "verification_label": "MISSING",
      "outcome": "UNVERIFIED",
      "evidence_refs": []
    }
  ]
}
```

## Banking sample

```json
{
  "affected_entity": "TRF-3101",
  "expected_path": ["transfer_accepted", "debit_posted", "credit_posted"],
  "verified_completed_steps": ["transfer_accepted", "debit_posted"],
  "last_successful_step": "debit_posted",
  "first_failed_or_missing_step": "credit_posted",
  "responsible_component": "CreditPostingWorker",
  "remaining_gap": "Causal evidence is still required for failed step Credit Posted.",
  "nodes": [
    {
      "step_id": "credit_posted",
      "verification_label": "RUNTIME_VERIFIED",
      "outcome": "FAILED",
      "evidence_refs": ["LOG-CREDIT"]
    }
  ]
}
```

## Shipping sample

```json
{
  "affected_entity": "SHP-5001",
  "expected_path": ["booking_created", "label_generated", "shipment_dispatched"],
  "verified_completed_steps": [
    "booking_created",
    "label_generated",
    "shipment_dispatched"
  ],
  "last_successful_step": "shipment_dispatched",
  "first_failed_or_missing_step": "",
  "responsible_component": "",
  "remaining_gap": "",
  "status": "COMPLETE"
}
```

Procedure definitions, function dependencies, trigger metadata, and job configuration can
place a step in the expected path, but those sources remain `METADATA_ONLY` until runtime or
data-state evidence proves execution.
