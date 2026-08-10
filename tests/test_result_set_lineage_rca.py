from legacydb_copilot.agents.reasoning_agent import RootCauseSupportStatus
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.result_set_lineage_service import (
    RowExclusionStatus,
    evaluate_row_exclusion_candidates,
    extract_output_target,
    parse_result_set_lineage,
    plan_row_exclusion_verification,
    resolve_output_producers,
    row_exclusion_reasoning,
)
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


def _procedure(name: str, definition: str, *, reads=(), writes=()) -> ProcedureAnalysis:
    return ProcedureAnalysis(
        name=name,
        definition_available=True,
        tables_read=list(reads),
        tables_written=list(writes),
        joins=definition.lower().count(" join "),
        insert_statements=0,
        update_statements=0,
        delete_statements=0,
        merge_statements=0,
        loops=0,
        transactions=0,
        try_catch=False,
        rollback_statements=0,
        cursors=0,
        temp_tables=0,
        dynamic_sql=False,
        missing_exists_checks=False,
        missing_uniqueness_checks=False,
        deadlock_risk="Low",
        locking_risk="Low",
        complexity_score=1,
        complexity="Low",
        business_rules=[],
        definition_excerpt=definition,
        definition=definition,
    )


def _producer(definition: str):
    target = extract_output_target("Why is RecordId 1 missing from the monthly summary for 2026?")
    procedures = [
        _procedure(
            "dbo.usp_CreateRecord",
            "CREATE PROC x AS INSERT INTO dbo.Records VALUES (1)",
            writes=("dbo.Records",),
        ),
        _procedure("dbo.usp_GetMonthlySummary", definition, reads=("dbo.Records",)),
    ]
    candidates = resolve_output_producers(target, procedures, entity_table="dbo.Records")
    assert candidates[0].producer_object == "dbo.usp_GetMonthlySummary"
    return target, candidates[0]


def test_extracts_structured_missing_output_target() -> None:
    target = extract_output_target(
        "Why is EmployeeId 7 not appearing in the payroll report for 2025?"
    )
    assert target is not None
    assert target.symptom_type == "MISSING_FROM_OUTPUT"
    assert target.output_phrase == "payroll report"
    assert target.qualifiers["years"] == [2025]


def test_inner_join_absence_is_parameterized_and_verified() -> None:
    target, producer = _producer(
        "CREATE PROC dbo.usp_GetMonthlySummary @Year int AS "
        "SELECT r.RecordId FROM dbo.Records r INNER JOIN dbo.Details d ON d.RecordId=r.RecordId "
        "WHERE YEAR(r.CreatedAt)=@Year"
    )
    candidates, queries = plan_row_exclusion_verification(
        target=target,
        producer=producer,
        entity_table="dbo.Records",
        identifier_column="RecordId",
        identifier_value=1,
    )
    join_candidate = next(
        item for item in candidates if item.candidate_type == "INNER_JOIN_RELATED_ROW_ABSENCE"
    )
    assert "LEFT JOIN dbo.Details d" in join_candidate.verification_query
    assert ":output_entity_identifier" in join_candidate.verification_query
    assert "RecordId = 1" not in join_candidate.verification_query
    evidence = [
        EvidenceResult(
            "Entity exact lookup in dbo.Records by RecordId",
            "SELECT RecordId FROM dbo.Records WHERE RecordId=:id",
            [{"RecordId": 1}],
            evidence_id="SQL-1",
            row_scope="exact_identifier",
        ),
        EvidenceResult(
            queries[0].purpose,
            queries[0].sql,
            [],
            evidence_id="SQL-2",
            evidence_semantics="verified_absence",
        ),
        EvidenceResult(
            f"Row exclusion verification {join_candidate.candidate_id}",
            join_candidate.verification_query,
            [{"RecordId": 1, "exclusion_condition_met": 1}],
            evidence_id="SQL-3",
        ),
        EvidenceResult(
            "Inspect calculation logic in dbo.usp_GetMonthlySummary",
            "",
            [{"definition_excerpt": "SELECT"}],
            evidence_id="PROC-1",
        ),
    ]
    evaluated = evaluate_row_exclusion_candidates(candidates, evidence, producer)
    verified = next(
        item for item in evaluated if item.candidate_type == "INNER_JOIN_RELATED_ROW_ABSENCE"
    )
    assert verified.status is RowExclusionStatus.VERIFIED
    assert verified.supporting_evidence_ids == ("SQL-1", "SQL-2", "SQL-3", "PROC-1")
    reasoning = row_exclusion_reasoning(evaluated, producer, evidence)
    assert reasoning.response_type == "confirmed_root_cause"
    assert reasoning.likely_root_causes[0].status is RootCauseSupportStatus.VERIFIED


def test_where_rejection_generates_exact_predicate_probe() -> None:
    target, producer = _producer(
        "CREATE PROC dbo.usp_GetMonthlySummary AS SELECT r.RecordId FROM dbo.Records r "
        "WHERE r.Status = 'ACTIVE'"
    )
    candidates, _ = plan_row_exclusion_verification(
        target=target,
        producer=producer,
        entity_table="dbo.Records",
        identifier_column="RecordId",
        identifier_value=7,
    )
    candidate = next(
        item for item in candidates if item.candidate_type == "WHERE_PREDICATE_REJECTION"
    )
    assert "CASE WHEN (r.Status = 'ACTIVE') THEN 0 ELSE 1" in candidate.verification_query
    assert candidate.verification_parameters["output_entity_identifier"] == 7


def test_date_range_exclusion_binds_year_parameter() -> None:
    target, producer = _producer(
        "CREATE PROC dbo.usp_GetMonthlySummary @ReportYear int AS "
        "SELECT r.RecordId FROM dbo.Records r "
        "WHERE YEAR(r.CreatedAt) = @ReportYear"
    )
    candidates, queries = plan_row_exclusion_verification(
        target=target,
        producer=producer,
        entity_table="dbo.Records",
        identifier_column="RecordId",
        identifier_value=3,
    )
    where_candidate = next(
        item for item in candidates if item.candidate_type == "WHERE_PREDICATE_REJECTION"
    )
    assert "@ReportYear" not in where_candidate.verification_query
    assert ":output_reportyear" in where_candidate.verification_query
    assert where_candidate.verification_parameters["output_reportyear"] == 2026
    assert queries[0].row_scope == "exact_output_membership"


def test_not_exists_anti_join_is_structured_and_planned() -> None:
    target, producer = _producer(
        "CREATE PROC dbo.usp_GetMonthlySummary AS SELECT r.RecordId FROM dbo.Records r "
        "WHERE NOT EXISTS (SELECT 1 FROM dbo.Blocks b WHERE b.RecordId=r.RecordId)"
    )
    assert producer.lineage.anti_join_predicates
    candidates, _ = plan_row_exclusion_verification(
        target=target,
        producer=producer,
        entity_table="dbo.Records",
        identifier_column="RecordId",
        identifier_value=9,
    )
    anti = next(item for item in candidates if item.candidate_type == "ANTI_JOIN_NOT_EXISTS")
    assert "CASE WHEN EXISTS" in anti.verification_query
    assert anti.verification_parameters == {"output_entity_identifier": 9}


def test_parser_persists_join_filter_group_having_alias_and_parameters() -> None:
    lineage = parse_result_set_lineage(
        "dbo.usp_Output",
        "CREATE PROC dbo.usp_Output @Minimum int AS SELECT r.Status, COUNT(*) AS Total "
        "FROM dbo.Records r LEFT JOIN dbo.Details d ON d.RecordId=r.RecordId "
        "WHERE r.IsVisible=1 GROUP BY r.Status HAVING COUNT(*) > @Minimum",
    )
    value = lineage.to_dict()
    assert value["joins"][0]["join_type"] == "LEFT"
    assert value["where_predicate"] == "r.IsVisible=1"
    assert value["group_by"] == ("r.Status",)
    assert value["having_predicate"] == "COUNT(*) > @Minimum"
    assert "Total" in value["output_aliases"]
    assert value["parameters"] == ("@Minimum",)


def test_having_rejection_preserves_grouped_output_semantics() -> None:
    target, producer = _producer(
        "CREATE PROC dbo.usp_GetMonthlySummary @Minimum int AS "
        "SELECT r.RecordId, COUNT(*) AS Total FROM dbo.Records r "
        "GROUP BY r.RecordId HAVING COUNT(*) > @Minimum"
    )
    target = type(target)(
        target.symptom_type,
        target.output_phrase,
        target.source_text,
        target.confidence,
        {"years": [], "parameters": {"minimum": 2}},
    )
    candidates, queries = plan_row_exclusion_verification(
        target=target,
        producer=producer,
        entity_table="dbo.Records",
        identifier_column="RecordId",
        identifier_value=4,
    )
    assert "GROUP BY r.RecordId" in queries[0].sql
    assert "HAVING COUNT(*) > :output_minimum" in queries[0].sql
    assert queries[0].parameters["output_minimum"] == 2
    having = next(
        item for item in candidates if item.candidate_type == "HAVING_PREDICATE_REJECTION"
    )
    assert "GROUP BY r.RecordId" in having.verification_query
