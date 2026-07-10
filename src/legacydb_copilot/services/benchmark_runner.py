from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.hypothesis_agent import run_hypothesis_investigation
from legacydb_copilot.agents.intent_agent import detect_intent
from legacydb_copilot.agents.investigation_planner_agent import build_investigation_plan
from legacydb_copilot.agents.object_ranking_agent import rank_relevant_objects
from legacydb_copilot.agents.reasoning_agent import reason_about_evidence
from legacydb_copilot.services.evidence_correlation_service import correlate_evidence
from legacydb_copilot.services.evidence_execution_service import execute_evidence_plan
from legacydb_copilot.services.evidence_focus_service import build_evidence_focus
from legacydb_copilot.services.evidence_gate_service import run_evidence_gate
from legacydb_copilot.services.evidence_verification_agent import (
    execute_verification_check,
    suggest_verification_checks,
)
from legacydb_copilot.services.metadata_search_service import search_metadata
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.safe_sql_service import validate_read_only_sql
from legacydb_copilot.services.stored_procedure_intelligence import analyze_stored_procedures


@dataclass(frozen=True)
class ExpectedIssue:
    issue_id: str
    question: str
    business_key: str
    affected_object: str
    expected_root_cause: str
    expected_procedure: str
    expected_evidence: str
    issue_type: str


@dataclass(frozen=True)
class BenchmarkCaseResult:
    issue_id: str
    question: str
    affected_object_match: bool
    procedure_match: bool
    evidence_verified: bool
    root_cause_score: float
    verification_score: float
    overall_score: float
    notes: list[str]


@dataclass(frozen=True)
class BenchmarkRunResult:
    case_results: list[BenchmarkCaseResult]
    metrics: dict[str, float]


@dataclass(frozen=True)
class GoldenScenarioBenchmarkResult:
    entity_correct: bool
    relevant_object_found: bool
    evidence_linked: bool
    root_cause_supported: bool
    unsupported_claim_count: int
    unsupported_recommendation_count: int
    test_passed: bool

    def __post_init__(self) -> None:
        if self.unsupported_claim_count < 0 or self.unsupported_recommendation_count < 0:
            raise ValueError("Unsupported item counts cannot be negative.")

    def to_dict(self) -> dict[str, bool | int]:
        return asdict(self)

    def to_markdown(self) -> str:
        values = self.to_dict()
        rows = [f"| {name} | {str(value).lower() if isinstance(value, bool) else value} |" for name, value in values.items()]
        return "\n".join(
            [
                "# Duplicate-payment golden benchmark",
                "",
                "Single deterministic golden-scenario result. This is not a production-accuracy claim.",
                "",
                "| Metric | Result |",
                "|---|---:|",
                *rows,
                "",
            ]
        )


def assert_demo_database(connection_string: str, *, allow_customer_db: bool = False) -> None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles assert demo database within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    if allow_customer_db:
        return
    parsed = urlparse(connection_string.replace("mysql+pymysql://", "mysql://", 1))
    database = (parsed.path or "").strip("/").lower()
    safe_markers = ("demo", "test", "benchmark", "sample", "sandbox")
    if not any(marker in database for marker in safe_markers):
        raise ValueError(
            "Benchmark runner is demo-only. Refusing to run because database name does not "
            "contain demo/test/benchmark/sample/sandbox."
        )


def load_expected_issues(connector) -> list[ExpectedIssue]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles load expected issues within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    rows = connector.execute_read_only_query(
        """
SELECT
    issue_id,
    question,
    business_key,
    affected_object,
    expected_root_cause,
    expected_procedure,
    expected_evidence,
    issue_type
FROM ai_expected_issues
ORDER BY issue_id
""".strip(),
        limit=100,
    )
    return [ExpectedIssue(**row) for row in rows]


def run_benchmark(connector, *, connection_string: str = "", allow_customer_db: bool = False) -> BenchmarkRunResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Handles run benchmark within the Database Support AI application flow.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Investigation, reporting, verification, or knowledge workflows as needed.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    if connection_string:
        assert_demo_database(connection_string, allow_customer_db=allow_customer_db)
    issues = load_expected_issues(connector)
    results = [_run_case(connector, issue) for issue in issues]
    return BenchmarkRunResult(case_results=results, metrics=_metrics(results))


def _run_case(connector, issue: ExpectedIssue) -> BenchmarkCaseResult:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for run case within benchmark_runner.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in benchmark_runner.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    entities = extract_entities(issue.question)
    intent = detect_intent(issue.question)
    metadata = search_metadata(connector, issue.question, entities)
    documents: list[RetrievedDocument] = []
    ranking = rank_relevant_objects(question=issue.question, intent=intent, entities=entities, metadata=metadata)
    procedure_analysis = analyze_stored_procedures(connector, ranking.metadata.procedures)
    plan = build_investigation_plan(intent.intent, ranking.metadata, entities)
    _validate_plan_read_only(plan)
    evidence = execute_evidence_plan(connector, plan)
    correlated = correlate_evidence(
        evidence=evidence,
        procedure_analysis=procedure_analysis,
        documents=documents,
    )
    focus = build_evidence_focus(
        question=issue.question,
        intent=intent.intent,
        entities=entities,
        metadata=ranking.metadata,
        evidence=evidence,
        correlated_evidence=correlated,
        procedure_analysis=procedure_analysis,
        documents=documents,
    )
    gate = run_evidence_gate(
        question=issue.question,
        intent=intent.intent,
        entities=entities,
        metadata=ranking.metadata,
        evidence=evidence,
        evidence_focus=focus,
        documents=documents,
    )
    hypothesis = run_hypothesis_investigation(
        question=issue.question,
        intent=intent,
        entities=entities,
        ranked_objects=ranking.objects,
        metadata=ranking.metadata,
        evidence=evidence,
        correlated_evidence=correlated,
        procedure_analysis=procedure_analysis,
        documents=documents,
    )
    reasoning = reason_about_evidence(
        issue.question,
        intent,
        entities,
        ranking.metadata,
        evidence,
        documents,
        correlated,
        procedure_analysis,
        focus,
    )
    suggestions = suggest_verification_checks(
        question=issue.question,
        intent=intent.intent,
        metadata=ranking.metadata,
        evidence=evidence,
        evidence_focus=focus,
        evidence_gate=gate,
        procedure_analysis=procedure_analysis,
        documents=documents,
        reasoning=reasoning,
    )
    verification_results = []
    for check in suggestions:
        verification_results.extend(
            execute_verification_check(
                connector=connector,
                claim=check.claim,
                verification_sql=check.verification_sql,
                expected_result=check.expected_result,
                source=check.source,
                verified_by="benchmark",
            )
        )
    affected_match = focus.affected_object.lower() == issue.affected_object.lower()
    procedure_match = any(
        rank.procedure.lower() == issue.expected_procedure.lower()
        and rank.writes_affected_object
        for rank in focus.ranked_procedures
    )
    verification_score = _verification_score(verification_results)
    root_cause_score = _text_overlap_score(
        " ".join([claim.conclusion for claim in reasoning.likely_root_causes] + hypothesis.event_chain),
        f"{issue.expected_root_cause} {issue.expected_evidence}",
    )
    evidence_verified = any(result.status == "Verified" for result in verification_results)
    overall = (
        (0.25 if affected_match else 0.0)
        + (0.25 if procedure_match else 0.0)
        + root_cause_score * 0.25
        + verification_score * 0.25
    )
    notes = [
        f"Detected intent: {intent.intent.value}",
        f"Affected object: {focus.affected_object}",
        f"Top procedure: {focus.ranked_procedures[0].procedure if focus.ranked_procedures else 'none'}",
        f"Evidence gate reproduced: {gate.reproduced}",
    ]
    return BenchmarkCaseResult(
        issue_id=issue.issue_id,
        question=issue.question,
        affected_object_match=affected_match,
        procedure_match=procedure_match,
        evidence_verified=evidence_verified,
        root_cause_score=round(root_cause_score, 3),
        verification_score=round(verification_score, 3),
        overall_score=round(overall, 3),
        notes=notes,
    )


def _validate_plan_read_only(plan) -> None:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for validate plan read only within benchmark_runner.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in benchmark_runner.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    for query in plan:
        validate_read_only_sql(query.sql)


def _verification_score(results) -> float:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verification score within benchmark_runner.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in benchmark_runner.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    if not results:
        return 0.0
    values = {
        "Verified": 1.0,
        "Partially Verified": 0.5,
        "Not Enough Evidence": 0.25,
        "Not Verified": 0.0,
    }
    return sum(values.get(result.status, 0.0) for result in results) / len(results)


def _text_overlap_score(actual: str, expected: str) -> float:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for text overlap score within benchmark_runner.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in benchmark_runner.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    actual_terms = _terms(actual)
    expected_terms = _terms(expected)
    if not expected_terms:
        return 0.0
    return len(actual_terms & expected_terms) / len(expected_terms)


def _terms(text: str) -> set[str]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for terms within benchmark_runner.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in benchmark_runner.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    stop = {"the", "and", "for", "with", "from", "that", "this", "into", "because", "should"}
    return {term for term in "".join(ch.lower() if ch.isalnum() or ch == "_" else " " for ch in text).split() if len(term) > 3 and term not in stop}


def _metrics(results: list[BenchmarkCaseResult]) -> dict[str, float]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for metrics within benchmark_runner.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in benchmark_runner.py.
    
    Where it fits in the flow:
        Application orchestration -> service function -> structured result for the next workflow step.
    
    Safety considerations:
        Keep tenant/workspace boundaries and do not introduce unsafe database or secret handling.
    """
    if not results:
        return {
            "case_count": 0.0,
            "affected_object_accuracy": 0.0,
            "procedure_accuracy": 0.0,
            "evidence_verification_rate": 0.0,
            "average_root_cause_score": 0.0,
            "average_overall_score": 0.0,
        }
    count = float(len(results))
    return {
        "case_count": count,
        "affected_object_accuracy": sum(1 for item in results if item.affected_object_match) / count,
        "procedure_accuracy": sum(1 for item in results if item.procedure_match) / count,
        "evidence_verification_rate": sum(1 for item in results if item.evidence_verified) / count,
        "average_root_cause_score": sum(item.root_cause_score for item in results) / count,
        "average_overall_score": sum(item.overall_score for item in results) / count,
    }
