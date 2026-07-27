# Deterministic Evidence Gap Detection

Evidence-gap detection runs after deterministic evidence execution, verification, stored
procedure analysis, and Evidence Gate evaluation. It does not execute SQL and does not
change any deterministic finding.

## Detection rules

- A successful zero-row result explicitly classified as `verified_absence` is evidence.
- Failed and policy-blocked queries remain unresolved; neither is absence evidence.
- Object or procedure definitions establish metadata only. They do not establish runtime
  execution.
- Contradictory verified evidence keeps the affected question open until reconciled.
- Application logs, message queues, and other unavailable runtime sources are classified as
  external evidence and may result in `BLOCKED_BY_MISSING_SOURCE`.
- A question is answered only by evidence relevant to that question.

Each open gap records its question type, priority, goal requirement, status, source type,
supporting evidence references, recommended next evidence, and reason. The serialized
analysis is stored on the investigation, returned by the investigation detail API, and
included in the report's structured evidence-gap section.

## Example

```json
{
  "status": "GAPS_IDENTIFIED",
  "gaps": [
    {
      "gap_id": "GAP-RUNTIME_EXECUTION",
      "question_type": "RUNTIME_EXECUTION",
      "priority": "HIGH",
      "required_for_goal": true,
      "status": "BLOCKED_BY_MISSING_SOURCE",
      "source_type": "EXTERNAL",
      "supporting_evidence_refs": ["EV-104"],
      "recommended_next_evidence": {
        "source_type": "EXTERNAL",
        "evidence_type": "EXTERNAL_RUNTIME_EVIDENCE",
        "description": "Obtain the scoped application log, message-queue trace, or external runtime record."
      },
      "reason": "Database metadata does not prove that the runtime operation executed."
    }
  ],
  "answered_questions": ["AFFECTED_ENTITY", "ACTUAL_STATE"],
  "evidence_summary": {
    "verified_runtime": 1,
    "verified_absence": 0,
    "metadata_only": 1,
    "failed_queries": 0,
    "blocked_queries": 0,
    "contradictions": 0,
    "external_evidence": 0
  }
}
```
