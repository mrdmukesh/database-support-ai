# Evidence Gate and Reasoning Dispatch Policy

The Evidence Gate and Reasoning Dispatcher have separate responsibilities.

## Evidence Gate

The gate evaluates deterministic state and emits only a permission:

- `ALLOW_REASONING`: at least one safe SQL statement returned relevant verified rows, the requested key (when
  supplied) exists in those rows, and the rows belong to the affected evidence scope.
- `DENY_REASONING`: verified deterministic SQL rows are unavailable, the requested key was not established, or
  the evidence does not cover the affected scope.

Metadata, retrieved documents, or procedure definitions alone do not permit provider reasoning. SQL errors do
not become evidence. A successful query with no rows does not become evidence. Existing intent-specific
reproduction checks remain intact and continue to determine whether the reported condition was reproduced.

The gate does not select an LLM prompt or reasoning mode.

## Reasoning Dispatcher

After permission is known, the dispatcher selects exactly one mode:

| Verified evidence | Issue reproduced | Permission | Invoke provider | Mode |
|---|---:|---|---:|---|
| No | No | `DENY_REASONING` | No | `SKIP` |
| No | Yes | `DENY_REASONING` | No | `SKIP` |
| Yes | Yes | `ALLOW_REASONING` | Yes | `NORMAL_ROOT_CAUSE` |
| Yes | No | `ALLOW_REASONING` | Yes | `EVIDENCE_SUMMARY_NOT_REPRODUCED` |

This decision uses investigation state, never a domain, schema, table, business key, benchmark identifier, intent
wording, or question phrase.

## Constrained summary mode

`EVIDENCE_SUMMARY_NOT_REPRODUCED` may summarize only verified evidence, factual chronology, confirmed facts, and
missing evidence. It must say that the reported condition was not reproduced. The application forcibly retains
the deterministic no-root-cause conclusion, investigation-only recommendations, and proof-of-fix restrictions,
even if a provider response attempts to return a root cause or fix.

## Preserved controls

- SQL is still produced and executed only by the safe read-only planner and validator.
- Entity/key and affected-row checks still precede permission.
- Intent-specific reproduction checks are unchanged.
- Provider prompts are masked and invocation-audited.
- Provider claims still undergo citation validation.
- A denied investigation never calls the provider and never creates an invocation row.
- Provider configuration and failure fallbacks remain deterministic.
