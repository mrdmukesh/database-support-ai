# Reasoning Invocation Architecture

## Execution path and prevention points

```text
User question
  -> safety analysis
  -> intent detection
     -> metadata validation mode? deterministic return
     -> knowledge search mode? deterministic/RAG return
     -> business-rule discovery mode? deterministic return
  -> workspace connection lookup
     -> no connection? deny/return
  -> database connection and active-schema validation
     -> connection or schema failure? deny/return
  -> metadata discovery (optional audited embedding provider call)
     -> explicit target absent? deny/return
  -> entity resolution
     -> not found, ambiguous, or blocked? deny/return
  -> target selection and relationship discovery
     -> requested business identifier but no relevant object? deny/return
  -> safe SQL planning
     -> unsafe candidates rejected individually
     -> no validated query? planning-failed result
  -> read-only SQL execution
     -> failures recorded, never promoted to evidence
  -> related evidence expansion and correlation
  -> deterministic evidence focus and verification
  -> Evidence Gate
     -> ALLOW_REASONING
     -> DENY_REASONING -> deterministic report, no provider/audit row
  -> Reasoning Dispatcher
     -> reproduced -> NORMAL_ROOT_CAUSE
     -> not reproduced -> EVIDENCE_SUMMARY_NOT_REPRODUCED
  -> centralized audited LLM provider client
     -> disabled? deterministic policy fallback
     -> failure/timeout? deterministic failure fallback and failed audit row
     -> success? citation validation and safe merge
  -> recommendations and verification suggestions
  -> report composer
  -> investigation/audit persistence
```

## Before

```text
Evidence Gate
  + validates evidence
  + evaluates reproduction
  + inspects intent and question wording
  + sets summary_mode_eligible
        |
        + false -> skip provider
        + true  -> constrained provider call
```

This mixed permission with prompt selection. Equivalent verified state could receive different behavior because
of intent or wording.

## After

```text
                    deterministic evidence
                             |
                      Evidence Gate
                  ALLOW_REASONING / DENY_REASONING
                             |
                    Reasoning Dispatcher
             +---------------+----------------+
             |                                |
       issue reproduced                issue not reproduced
       NORMAL_ROOT_CAUSE          EVIDENCE_SUMMARY_NOT_REPRODUCED
             |                                |
             +---------- audited provider ----+
```

The gate owns permission. The dispatcher owns mode. The provider layer owns only execution and auditing.

## Provider invocation paths

1. Metadata discovery may call the configured embedding provider through `AuditedLLMProviderClient`.
2. Investigation reasoning calls the Responses provider through `enhance_reasoning_with_llm`, using the mode
   selected by `dispatch_reasoning`.
3. Evaluation AI Judge calls use the same centralized provider boundary but are not part of the investigation
   reasoning decision.

There are no direct investigation provider calls outside the centralized audited client.

## Persisted diagnostics

The sanitized AI trace records:

- `reasoning_permission`
- `reasoning_mode`
- `reasoning_dispatch_reason`
- verified-evidence and reproduction fields
- evidence-plan statuses and counts
- provider attempt/outcome and token usage
- accepted and rejected cited claims

No raw credentials, authorization data, connection strings, or unsanitized row payloads are persisted.
