# Root Cause Hypothesis Verification (AG-07)

AG-07 treats every proposed root cause—deterministic or AI-generated—as a candidate until
each required causal link is independently verified.

## Hypothesis model

Each hypothesis records:

- affected entity or scope;
- expected state;
- incorrect actual state;
- last successful step from AG-06;
- first failed, missing, or inconsistent step from AG-06;
- responsible component;
- causal condition;
- supporting evidence references;
- missing proof;
- material contradictions;
- origin (`DETERMINISTIC` or `LLM`).

Each causal link contains its value, evidence references, and an independent-verification
flag. The verifier validates every reference against successful, relevant evidence.

## Classification rules

- `PROPOSED`: no causal link has independent proof.
- `PARTIALLY_SUPPORTED`: some links are verified, but at least one required link is missing.
- `CONFIRMED`: all seven required links are independently verified, actual state is proven
  incorrect, evidence references are valid, causation is positive, and material
  contradictions are resolved.
- `REJECTED`: claimed references are invalid/unverified, or an AI causal claim lacks
  independently verified causal evidence.
- `BLOCKED`: affected entity/scope is unresolved or a material contradiction remains.

Successful zero-row evidence may verify an incorrect missing state. It cannot, by itself,
prove why the state occurred. Likewise, procedure, trigger, function, dependency, or job
metadata cannot prove runtime execution or component responsibility.

Only `CONFIRMED` hypotheses have `visible_in_report=true`. When a verification matrix is
attached to a report bundle, legacy confidence-ranked and rejected candidates are excluded
from visible root-cause and hypothesis sections.

## Confirmed example

```json
{
  "hypothesis_id": "H-PAYROLL-1",
  "description": "The verified eligibility guard excluded EMP-1001 before PayrollItem creation.",
  "origin": "DETERMINISTIC",
  "status": "CONFIRMED",
  "visible_in_report": true,
  "verification_matrix": [
    {"link_name": "affected_entity", "verified": true, "valid_evidence_refs": ["SQL-ENTITY"]},
    {"link_name": "expected_state", "verified": true, "valid_evidence_refs": ["RULE-EXPECTED"]},
    {"link_name": "actual_state", "verified": true, "valid_evidence_refs": ["SQL-ABSENCE"]},
    {"link_name": "last_successful_step", "verified": true, "valid_evidence_refs": ["SQL-READY"]},
    {"link_name": "first_failed_step", "verified": true, "valid_evidence_refs": ["LOG-FAIL"]},
    {"link_name": "responsible_component", "verified": true, "valid_evidence_refs": ["LOG-WORKER"]},
    {"link_name": "causal_condition", "verified": true, "valid_evidence_refs": ["SQL-GUARD"]}
  ],
  "missing_proof": [],
  "contradictions": []
}
```

## Rejected example

```json
{
  "hypothesis_id": "H-AI-2",
  "description": "An AI-proposed worker timeout caused PayrollItem creation to fail.",
  "origin": "LLM",
  "status": "REJECTED",
  "visible_in_report": false,
  "verification_matrix": [
    {
      "link_name": "causal_condition",
      "verified": false,
      "valid_evidence_refs": [],
      "invalid_evidence_refs": ["EV-NOT-REAL"],
      "reason": "Evidence references are missing, failed, blocked, or irrelevant."
    }
  ],
  "decision_reason": "The AI-proposed causal claim lacks independently verified causal evidence."
}
```

Migration `0018_hypothesis_verify` stores the full hypothesis, verification matrix, valid
references, missing proof, contradictions, evidence-package hash, decision reason, origin,
status, and report-visibility decision. The audit log records confirmed and rejected IDs.
