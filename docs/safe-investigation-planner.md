# Safe Investigation Planner

The Safe Investigation Planner runs after deterministic gap detection and chooses one
logical evidence action. It does not contain or generate SQL. The selected
`EvidenceRequest` is passed to the existing provider-specific planner, SQL validator, and
executor.

## Selection algorithm

Eligible requests are ordered deterministically by:

1. required-for-goal status;
2. investigation sequence: affected entity, expected state, actual state, relationships,
   workflow, last successful step, first failed step, dependency logic, then runtime evidence;
3. narrow entity scope;
4. expected information gain;
5. estimated query cost and broad-scan risk;
6. stable request-type and fingerprint tie breakers.

Environment policy and query/iteration budgets are hard gates. The canonical SHA-256 action
fingerprint excludes ranking metadata and includes only the logical action target. Completed,
permanently failed, and already-selected duplicates are suppressed. A classified transient
failure receives at most one controlled retry. Repeated broad metadata and table-scan actions
are therefore not selected.

Selections are stored in `investigation_planner_selections`, including the logical request,
fingerprint, selection reason, expected information gain, retry number, and ranking audit.

## Example planner audit

```json
{
  "status": "SELECTED",
  "action_fingerprint": "5f327b2b...d104",
  "evidence_request": {
    "request_type": "ENTITY_LOOKUP",
    "unresolved_question": "AFFECTED_ENTITY",
    "entity_scope": "EXACT_KEY",
    "entity_type": "Order",
    "entity_key": "ORD-42",
    "supporting_evidence_refs": ["EV-ENTITY-CANDIDATE-1"]
  },
  "selection_reason": "Selected required question AFFECTED_ENTITY; scope=EXACT_KEY, information_gain=0.90, cost=1, policy=evaluation_readonly.",
  "expected_information_gain": 0.9,
  "retry_number": 0,
  "suppressed_fingerprints": []
}
```
