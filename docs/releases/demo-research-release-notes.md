# Controlled demo and research release notes

## Purpose and scope

Classification: `CONTROLLED_DEMO_RESEARCH_RELEASE`.

This release supports demonstrations, research-paper evaluation, analyst-assisted investigations,
and controlled development or test use. It is not production-ready, autonomous, or approved for
unreviewed remediation. Every investigation requires human review.

## Source history

- Source branch: `feature/langgraph-workflow-evidence`
- Correctness baseline before release documentation:
  `37973fb57a60dde26a40683663b16d0737b8c4e5`
- Merge baseline: `47dad9433529c5232165e92b232c4eb68084a284`
- Release documentation is committed separately so benchmarked code remains identifiable.

## Delivered capabilities

- Typed LangGraph investigation state and controlled orchestration
- Entity and relationship discovery adapters
- Evidence-driven planning, bounded read-only SQL execution, and evidence gates
- Evidence-preserving reasoning and report composition
- Citation validation, contradiction rejection, and claim lifecycle auditing
- Central scan-policy decisions for related-ID expansion
- Evidence-backed response-type finalization and confidence calibration
- Controlled activation, kill switch, fallback, rollout, and comparison diagnostics
- Protected deterministic and AI-judge evaluation framework

## Validation evidence

Protected run `139aec7c-f934-461e-96ba-f25507555f62` completed 25/25 scenarios. Aggregate
deterministic classifications passed 25/25, with a 78.90% average. The AI judge averaged 64.18%.
Unsupported claims, safety failures, critical failures, confidence failures, and
evidence-integrity failures were all zero. Component validation still reported 16 response-type
mismatches and 11 root-cause mismatches.

The detailed scenario backlog and systemic analysis are in
`docs/releases/demo-research-release-known-limitations.md`.

## Deployment scope

Deploy only to named demo, research, development, or controlled test environments. Use read-only
customer-data credentials, workspace isolation, scan-policy enforcement, and an analyst approval
step. Do not enable unrestricted production traffic or automated data repair.

## Rollback guidance

The pre-merge code reference is `47dad9433529c5232165e92b232c4eb68084a284`. Disable
the application revision immediately to the prior LangGraph-only image. Preserve investigations,
evidence, reports, and audits.
If code rollback is required, redeploy the recorded pre-merge image/commit or revert the merge
commit; do not downgrade protected evaluation databases. See `docs/langgraph/rollback-runbook.md`.
