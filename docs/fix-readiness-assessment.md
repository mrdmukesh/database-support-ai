# AG-08 deterministic fix-readiness assessment

AG-08 determines whether the evidence package is mature enough for a SQL
developer to prepare a controlled corrective change. The informational score
never promotes an investigation past a missing prerequisite.

## Rules

- Only an AG-07 `CONFIRMED` hypothesis that is visible in the verified report
  satisfies the causal component and condition criterion.
- `REJECTED`, `BLOCKED`, `PROPOSED`, and `PARTIALLY_SUPPORTED` hypotheses cannot
  establish root cause.
- No resolved entity normally caps the outcome at `EVIDENCE_COLLECTED` or
  `INVESTIGATION_INCOMPLETE`.
- `FIX_PROPOSAL_READY` requires a confirmed root cause, controlled proposal,
  risk assessment, and pre-change checks.
- `PROOF_OF_FIX_READY` additionally requires post-fix validation and rollback.
- Runtime execution can be `NOT_REQUIRED` only when the deterministic
  investigation explicitly establishes that runtime proof is unnecessary.

Every result stores its criterion matrix, blockers, recommended next evidence,
confirmed hypothesis identifiers, score, and deterministic decision reason.
`GET /investigations/{investigation_id}/fix-readiness` returns the latest result.
The same report section is rendered in HTML, PDF, DOCX, and XLSX outputs.

## Before and after report example

Before causal confirmation:

```text
Readiness: ROOT_CAUSE_CANDIDATE
Informational score: 81% (prerequisites remain authoritative)
SQL developer may prepare a controlled change: No
Blocker: Independently verify the responsible component and causal condition.
```

After causal confirmation and change controls:

```text
Readiness: PROOF_OF_FIX_READY
Informational score: 100% (prerequisites remain authoritative)
SQL developer may prepare a controlled change: Yes
Decision: Confirmed cause, controlled fix, validation, and rollback are ready.
```

Older report bundles remain supported. When AG-08 data is absent, the report
shows a clearly labelled fallback state and directs the reader to run the
deterministic assessment; it does not fabricate criterion satisfaction.
