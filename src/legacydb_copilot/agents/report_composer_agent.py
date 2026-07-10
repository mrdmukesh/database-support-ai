from __future__ import annotations

import json

from legacydb_copilot.agents.intent_agent import InvestigationIntent
from legacydb_copilot.reports.dynamic_report_schema import DynamicInvestigationBundle
from legacydb_copilot.services.report_generator import (
    ExecutiveSummary,
    InvestigationReport,
    ReportCover,
    ReportSection,
    ReportSqlBlock,
    ReportTable,
    REPORT_VERSION,
    new_investigation_id,
    now_label,
)


def _evidence_tables(bundle: DynamicInvestigationBundle) -> list[ReportTable]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for evidence tables within report_composer_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in report_composer_agent.py.
    
    Where it fits in the flow:
        Evidence and reasoning bundle -> structured report -> HTML/PDF/DOCX/XLSX generators.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    tables: list[ReportTable] = []
    for item in bundle.evidence:
        if item.safety_note:
            tables.append(
                ReportTable(
                    title=f"{item.purpose} - SQL Safety",
                    columns=["Original SQL", "Executed SQL", "Reason"],
                    rows=[
                        {
                            "Original SQL": item.original_sql or item.sql,
                            "Executed SQL": item.sql,
                            "Reason": item.safety_note,
                        }
                    ],
                )
            )
        if item.rows:
            columns = list(item.rows[0].keys())
            tables.append(ReportTable(title=item.purpose, columns=columns, rows=item.rows[:10]))
        else:
            tables.append(
                ReportTable(
                    title=item.purpose,
                    columns=["SQL", "Result"],
                    rows=[{"SQL": item.sql, "Result": item.error or "No rows returned"}],
                )
            )
    return tables


def _sql_blocks(bundle: DynamicInvestigationBundle) -> list[ReportSqlBlock]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for sql blocks within report_composer_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in report_composer_agent.py.
    
    Where it fits in the flow:
        Evidence and reasoning bundle -> structured report -> HTML/PDF/DOCX/XLSX generators.
    
    Safety considerations:
        Must preserve read-only SQL behavior and never allow write commands or stored procedure execution.
    """
    return [
        ReportSqlBlock(
            purpose=item.purpose,
            expected_result=(
                "Rows should confirm or rule out the suspected issue. If no rows return, evidence is missing or object names differ."
                + (f" SQL changed from `{item.original_sql}`. Reason: {item.safety_note}" if item.safety_note and item.original_sql else "")
            ),
            risk="Read-only",
            sql=item.sql,
        )
        for item in bundle.evidence
    ]


def _missing_record_sections(bundle: DynamicInvestigationBundle) -> list[ReportSection]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for missing record sections within report_composer_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in report_composer_agent.py.
    
    Where it fits in the flow:
        Evidence and reasoning bundle -> structured report -> HTML/PDF/DOCX/XLSX generators.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    candidate = next((item for item in bundle.evidence if item.purpose == "Confirmed Missing Related Record Candidates"), None)
    summary = next((item for item in bundle.evidence if item.purpose == "Missing Related Record Summary by Issue Type"), None)
    if candidate is None:
        return []
    candidate_columns = list(candidate.rows[0].keys()) if candidate.rows else ["Result"]
    summary_columns = list(summary.rows[0].keys()) if summary and summary.rows else ["Issue Type", "Count", "Example Parent Keys"]
    return [
        ReportSection(
            title="Confirmed Missing Related Record Candidates",
            paragraphs=[
                "Business conclusion: the investigation found parent rows that are missing expected related child rows using discovered table relationships. Confirm the exact workflow guard or write path before applying a fix."
            ],
            tables=[
                ReportTable(
                    title="Missing Related Record Candidates",
                    columns=candidate_columns,
                    rows=candidate.rows[:50] if candidate.rows else [{"Result": candidate.error or "No missing related record candidates returned"}],
                ),
                ReportTable(
                    title="Missing Related Record Summary",
                    columns=summary_columns,
                    rows=summary.rows[:20] if summary and summary.rows else [{"Issue Type": "No summary rows", "Count": 0, "Example Parent Keys": ""}],
                ),
            ],
        )
    ]


def _intent_sections(bundle: DynamicInvestigationBundle) -> list[ReportSection]:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for intent sections within report_composer_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in report_composer_agent.py.
    
    Where it fits in the flow:
        Evidence and reasoning bundle -> structured report -> HTML/PDF/DOCX/XLSX generators.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    intent = bundle.intent.intent
    if intent == InvestigationIntent.PERFORMANCE_INVESTIGATION:
        has_plan = any("EXPLAIN" in f"{item.purpose} {item.sql}".upper() and (item.rows or item.error is None) for item in bundle.evidence)
        if not has_plan:
            return [
                ReportSection(
                    title="Performance Analysis",
                    items=["Performance advice is blocked until EXPLAIN or row-estimate evidence is collected from the connected database."],
                )
            ]
        return [
            ReportSection(title="Performance Analysis", items=[
                "EXPLAIN or row-estimate evidence was collected; review access type, selected index, possible indexes, estimated rows, and Extra details.",
                "Procedure scan risk should be judged only from parsed procedure read/write metadata and collected plan evidence.",
                "Optimization plan must cite the before/after evidence before recommending index or query changes.",
            ]),
        ]
    if intent == InvestigationIntent.PROCESS_FLOW_BREAK:
        return [ReportSection(title="Process Flow Analysis", items=[
            "Execution flow is inferred from procedure read/write order, returned status/state columns, validation branches, and documents.",
            "For each step, use the evidence tables to identify table, current status/state, responsible procedure, validation rule, and weak point.",
        ])]
    if intent == InvestigationIntent.DUPLICATE_DATA:
        return [ReportSection(title="Duplicate Data Analysis", items=["Review duplicate business keys, insert source, retry/idempotency controls, and uniqueness protection."])]
    if intent == InvestigationIntent.PRODUCTION_INVESTIGATION:
        return [ReportSection(title="Production Incident Analysis", items=["Use live database evidence, evidence gate results, affected-object discovery, and write-path ranking to explain the reported production condition."])]
    if intent == InvestigationIntent.MISSING_DATA:
        return [ReportSection(title="Missing Data Analysis", items=["Identify the expected record, upstream dependency, guard condition, and validation SQL."])]
    if intent == InvestigationIntent.FAILED_BATCH_JOB:
        return [ReportSection(title="Failed Batch Job Analysis", items=["Review batch status, failed step, error logs, related procedure, and retry/fix plan."])]
    if intent == InvestigationIntent.IMPACT_ANALYSIS:
        return [ReportSection(title="Impact Analysis", items=[
            "Analyze procedures, views, reports/queries, jobs, documents, and tests that reference the changed status/state/value/code.",
            "Do not recommend deployment until regression SQL, rollback, and dependent workflow tests are listed.",
        ])]
    if intent == InvestigationIntent.HEALTH_ASSESSMENT:
        categories = [
            "schema design",
            "indexing/performance",
            "stored procedures",
            "data quality",
            "batch processing",
            "security",
            "scalability",
            "maintainability",
        ]
        return [
            ReportSection(
                title="Health Assessment",
                items=[f"Score {category} separately using metadata, procedure analysis, evidence rows, and documents." for category in categories],
            )
        ]
    return [ReportSection(title="General Analysis", items=["Use available metadata and evidence to answer the database support question."])]


def _evidence_gate_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for evidence gate section within report_composer_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in report_composer_agent.py.
    
    Where it fits in the flow:
        Evidence and reasoning bundle -> structured report -> HTML/PDF/DOCX/XLSX generators.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    gate = bundle.evidence_gate
    if gate is None:
        return ReportSection(title="Evidence Gate", items=["Evidence gate was not available for this investigation."])
    rows = [
        {"Check": "Gate Required", "Result": "Yes" if gate.required else "No"},
        {"Check": "Issue Reproduced", "Result": "Yes" if gate.reproduced else "No"},
        {"Check": "Supplied Business Key Exists", "Result": "Yes" if gate.business_key_exists else "No"},
        {"Check": "Reported Condition Exists", "Result": "Yes" if gate.reported_condition_exists else "No"},
        {"Check": "Affected Rows Exist", "Result": "Yes" if gate.affected_rows_exist else "No"},
        {"Check": "Parent-Child Relationship Exists", "Result": "Yes" if gate.parent_child_relationship_exists else "No"},
    ]
    items = [*gate.confirmed_facts, *gate.status_interpretation]
    if gate.blocking_reasons:
        items.extend(gate.blocking_reasons)
    return ReportSection(
        title="Evidence Gate",
        paragraphs=[
            "Root-cause analysis is allowed only when the supplied key, affected rows, reported condition, and required relationships are supported by connected database evidence."
        ],
        items=items or ["No gate notes generated."],
        tables=[ReportTable(title="Gate Checks", columns=["Check", "Result"], rows=rows)],
    )


def _ai_reasoning_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for ai reasoning section within report_composer_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in report_composer_agent.py.
    
    Where it fits in the flow:
        Evidence and reasoning bundle -> structured report -> HTML/PDF/DOCX/XLSX generators.
    
    Safety considerations:
        Report generation must describe supplied evidence and must not execute SQL.
    """
    status = bundle.ai_reasoning_status or {
        "ai_assisted_reasoning": "Disabled",
        "reason": "AI reasoning status was not recorded for this investigation.",
        "evidence_package_sent": "No",
        "llm_evidence_validation": "Not applicable",
        "evidence_citations": "Not applicable",
    }
    rows = [
        {"Item": "AI-assisted reasoning", "Value": status.get("ai_assisted_reasoning", "Disabled")},
        {"Item": "Reason", "Value": status.get("reason", "")},
        {"Item": "Evidence package sent", "Value": status.get("evidence_package_sent", "No")},
        {"Item": "LLM evidence validation", "Value": status.get("llm_evidence_validation", "Not applicable")},
        {"Item": "Evidence citations", "Value": status.get("evidence_citations", "Not applicable")},
        {"Item": "PII masking", "Value": status.get("pii_masking", "Ready")},
        {"Item": "PII masking scope", "Value": status.get("pii_masking_scope", "Names, emails, phone numbers, insurance/account identifiers are masked before any LLM evidence package is sent.")},
    ]
    return ReportSection(
        title="AI Reasoning Status",
        tables=[ReportTable(title="AI-assisted Reasoning", columns=["Item", "Value"], rows=rows)],
    )


def _verification_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for verification section within report_composer_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in report_composer_agent.py.
    
    Where it fits in the flow:
        Evidence and reasoning bundle -> structured report -> HTML/PDF/DOCX/XLSX generators.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    rows = [
        {
            "Claim": item.claim,
            "Purpose": item.purpose,
            "Evidence logic": item.evidence_logic,
            "SQL executed": item.verification_sql,
            "Expected result": item.expected_result,
            "Actual result summary": item.actual_result_summary,
            "Interpretation": item.interpretation,
            "Conclusion": item.conclusion_template,
            "Status": item.status,
            "Confidence impact": item.confidence_impact,
            "Timestamp": item.timestamp,
            "Verified by": item.verified_by,
        }
        for item in (bundle.verification_results or [])
    ]
    return ReportSection(
        title="Evidence Verification Results",
        paragraphs=[
            "The verification agent checks root-cause claims, recommendations, and hypotheses against collected metadata, procedure analysis, documents, and read-only live SQL. It never executes writes or stored procedures."
        ],
        tables=[
            ReportTable(
                title="Evidence Verification Results",
                columns=[
                    "Claim",
                    "Purpose",
                    "Evidence logic",
                    "SQL executed",
                    "Expected result",
                    "Actual result summary",
                    "Interpretation",
                    "Conclusion",
                    "Status",
                    "Confidence impact",
                    "Timestamp",
                    "Verified by",
                ],
                rows=rows
                or [
                    {
                        "Claim": "No checks have been executed yet",
                        "Purpose": "",
                        "Evidence logic": "",
                        "SQL executed": "",
                        "Expected result": "",
                        "Actual result summary": "",
                        "Interpretation": "",
                        "Conclusion": "",
                        "Status": "Pending",
                        "Confidence impact": "",
                        "Timestamp": "",
                        "Verified by": "",
                    }
                ],
            )
        ],
    )


def _suggested_verification_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    """
    Owner: Mukesh Dabi
    Purpose:
        Internal helper for suggested verification section within report_composer_agent.py.
    
    Input:
        Function parameters declared in the signature.
    
    Output:
        Return value declared by the type hints or route response model.
    
    How it is called:
        Internal callers in report_composer_agent.py.
    
    Where it fits in the flow:
        Evidence and reasoning bundle -> structured report -> HTML/PDF/DOCX/XLSX generators.
    
    Safety considerations:
        Verification checks are suggested first and executed only after user approval through SafeSQLValidator.
    """
    rows = [
        {
            "Claim to verify": item.claim,
            "Purpose": item.purpose,
            "Claim being verified": item.claim_being_verified,
            "Evidence logic": item.evidence_logic,
            "Generated read-only SQL": item.verification_sql,
            "Expected result": item.expected_result,
            "Expected result explanation": item.expected_result_explanation,
            "Interpretation": item.interpretation,
            "Conclusion template": item.conclusion_template,
            "Risk level": item.risk_level,
            "Source": item.source,
            "Status": item.status,
        }
        for item in (bundle.verification_checks or [])
    ]
    return ReportSection(
        title="Suggested Verification Checks",
        paragraphs=[
            "These checks are suggestions only. A user must approve execution. The app validates every SQL statement before running it and allows only SELECT, SHOW, DESCRIBE, DESC, or EXPLAIN."
        ],
        tables=[
            ReportTable(
                title="Suggested Verification Checks",
                columns=[
                    "Claim to verify",
                    "Purpose",
                    "Claim being verified",
                    "Evidence logic",
                    "Generated read-only SQL",
                    "Expected result",
                    "Expected result explanation",
                    "Interpretation",
                    "Conclusion template",
                    "Risk level",
                    "Source",
                    "Status",
                ],
                rows=rows
                or [
                    {
                        "Claim to verify": "Verification suggestions disabled",
                        "Purpose": "",
                        "Claim being verified": "",
                        "Evidence logic": "",
                        "Generated read-only SQL": "",
                        "Expected result": "",
                        "Expected result explanation": "",
                        "Interpretation": "",
                        "Conclusion template": "",
                        "Risk level": "Read-only",
                        "Source": "",
                        "Status": "Pending",
                    }
                ],
            )
        ],
    )


def _strongest_evidence_rows(bundle: DynamicInvestigationBundle) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in bundle.evidence:
        if len(rows) >= 4:
            break
        if item.rows or item.safety_note or item.error:
            rows.append(
                {
                    "Evidence": item.purpose,
                    "Type": "SQL",
                    "Source": "Read-only evidence query",
                    "Summary": item.error or f"{len(item.rows)} row(s) returned",
                }
            )
    for proc in bundle.procedure_analysis:
        if len(rows) >= 4:
            break
        if proc.tables_written or proc.tables_read:
            rows.append(
                {
                    "Evidence": proc.name,
                    "Type": "Procedure",
                    "Source": ", ".join(proc.tables_written or proc.tables_read),
                    "Summary": f"Writes: {', '.join(proc.tables_written) or 'none'}; Reads: {', '.join(proc.tables_read) or 'none'}",
                }
            )
    return rows[:4]


def _executive_key_findings_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    focus = bundle.evidence_focus
    current_condition = next((fact for fact in bundle.reasoning.confirmed_facts if " row(s) returned" in fact or " has " in fact), "")
    parent_supporting = ""
    if bundle.metadata.tables:
        related = [
            table.name
            for table in bundle.metadata.tables[:6]
            if not focus or table.name != focus.affected_object
        ]
        parent_supporting = ", ".join(related[:3])
    rows = [
        {"Finding": "Affected object", "Value": focus.affected_object if focus else "Not determined"},
        {"Finding": "Business key", "Value": focus.inferred_business_key if focus and focus.inferred_business_key else "Not determined"},
        {"Finding": "Current status / duplicate / missing condition", "Value": current_condition or "See evidence summary and root cause analysis."},
        {"Finding": "Parent/supporting object", "Value": parent_supporting or "Not determined from available metadata."},
    ]
    return ReportSection(
        title="Key Findings",
        tables=[ReportTable(title="Key Findings", columns=["Finding", "Value"], rows=rows)],
    )


def _executive_evidence_summary_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    rows = _strongest_evidence_rows(bundle)
    return ReportSection(
        title="Top Evidence",
        paragraphs=["Strongest evidence items only. Detailed SQL checks, result samples, and verification SQL are in the full audit report."],
        tables=[
            ReportTable(
                title="Strongest Evidence",
                columns=["Evidence", "Type", "Source", "Summary"],
                rows=rows or [{"Evidence": "No evidence collected", "Type": "", "Source": "", "Summary": "No SQL/procedure evidence was available."}],
            )
        ],
    )


def _write_path_likely_procedure_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    ranked = bundle.evidence_focus.ranked_procedures if bundle.evidence_focus else []
    top = next((item for item in ranked if item.writes_affected_object), ranked[0] if ranked else None)
    if top is None:
        return ReportSection(title="Procedure Path", items=["No direct write procedure was confirmed from procedure metadata."])
    certainty = "Likely procedure" if top.writes_affected_object else "Related procedure only"
    return ReportSection(
        title="Procedure Path",
        items=[
            f"{certainty}: {top.procedure}",
            f"Writes affected object: {'Yes' if top.writes_affected_object else 'No'}",
            f"Evidence: {'; '.join(top.evidence_found[:4])}",
        ],
    )


def _executive_ai_reasoning_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    status = bundle.ai_reasoning_status or {}
    trace = bundle.ai_debug_trace or {}
    generated = len(trace.get("validated_citations") or []) + len(trace.get("rejected_or_unsupported_claims") or [])
    accepted = len(trace.get("validated_citations") or [])
    rejected = len(trace.get("rejected_or_unsupported_claims") or [])
    rows = [
        {"Item": "AI Reasoning", "Value": status.get("ai_assisted_reasoning", "Disabled")},
        {"Item": "Evidence Package", "Value": "Validated" if status.get("llm_evidence_validation") == "Passed" else status.get("llm_evidence_validation", "Not applicable")},
        {"Item": "LLM Claims", "Value": f"{generated} generated, {accepted} verified, {rejected} rejected"},
        {"Item": "Trace", "Value": "Full prompt available in Audit Trace." if trace else "Trace disabled or not available."},
    ]
    return ReportSection(
        title="AI Status",
        tables=[ReportTable(title="AI Reasoning Summary", columns=["Item", "Value"], rows=rows)],
    )


def _executive_fix_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    items = []
    items.extend(bundle.reasoning.recommended_fix[:3])
    if not items:
        items.extend(bundle.recommendation.immediate_fix[:2])
        items.extend(bundle.recommendation.permanent_fix[:2])
    return ReportSection(title="Fix", items=items or ["No fix recommended until evidence supports the reported condition."])


def _executive_tests_section(bundle: DynamicInvestigationBundle) -> ReportSection:
    rows = bundle.reasoning.test_cases[:5]
    return ReportSection(
        title="Tests",
        tables=[
            ReportTable(
                title="Recommended Tests",
                columns=["Test ID", "Scenario", "Steps", "Expected Result", "Actual Result", "Status"],
                rows=rows
                or [
                    {
                        "Test ID": "TC-001",
                        "Scenario": "Evidence validation",
                        "Steps": "Review the full audit report and execute approved read-only verification checks.",
                        "Expected Result": "Evidence supports the RCA before any fix is applied.",
                        "Actual Result": "Pending",
                        "Status": "Pending",
                    }
                ],
            )
        ],
    )


def _ai_reasoning_trace_section(bundle: DynamicInvestigationBundle) -> ReportSection | None:
    trace = bundle.ai_debug_trace or {}
    if not trace:
        return None
    validation_status = "PASSED" if not trace.get("rejected_or_unsupported_claims") else "PASSED WITH REJECTIONS"
    rows = [
        {"Item": "Model", "Value": str(trace.get("llm_model_name") or "")},
        {"Item": "Temperature", "Value": "0.1"},
        {"Item": "Validation", "Value": validation_status},
        {"Item": "Accepted Claims", "Value": str(len(trace.get("validated_citations") or []))},
        {"Item": "Rejected Claims", "Value": str(len(trace.get("rejected_or_unsupported_claims") or []))},
    ]
    return ReportSection(
        title="AI Reasoning Trace",
        paragraphs=[
            "Masked administrative trace. Database credentials, secrets, connection strings, emails, phone numbers, account identifiers, and customer PII are not stored in this trace."
        ],
        tables=[ReportTable(title="AI Trace Summary", columns=["Item", "Value"], rows=rows)],
        sql_blocks=[
            ReportSqlBlock("System Prompt", "Administrative audit only", "Masked", str(trace.get("system_prompt") or "")),
            ReportSqlBlock("User Prompt", "Administrative audit only", "Masked", str(trace.get("user_prompt") or "")),
            ReportSqlBlock("Evidence Before Masking Summary", "Summary only; raw PII is not stored", "Masked", json.dumps(trace.get("evidence_package_before_masking_summary") or {}, indent=2, default=str)),
            ReportSqlBlock("Evidence Sent To LLM", "Exact masked package received by OpenAI", "Masked", json.dumps(trace.get("evidence_package_after_masking") or {}, indent=2, default=str)),
            ReportSqlBlock("Raw AI Response", "Raw model response before application validation", "Masked", json.dumps(trace.get("llm_response_raw") or {}, indent=2, default=str)),
            ReportSqlBlock("Verification Result", "Accepted and rejected LLM claims with citation mapping", "Masked", json.dumps({"accepted": trace.get("validated_citations") or [], "rejected": trace.get("rejected_or_unsupported_claims") or [], "final_report_claims": trace.get("final_report_claims") or []}, indent=2, default=str)),
        ],
    )


def compose_report(
    *,
    bundle: DynamicInvestigationBundle,
    workspace_name: str,
    database_name: str,
    generated_by: str,
) -> InvestigationReport:
    """
    Owner: Mukesh Dabi
    Purpose:
        Converts the completed dynamic investigation bundle into the structured report object used for HTML, PDF,
        Word, and Excel generation.

    Input:
        DynamicInvestigationBundle plus workspace/database/generator identity.

    Output:
        InvestigationReport with cover page, evidence sections, reasoning, recommendations, verification checks,
        and appendices.

    Called by:
        Main /chat/ask orchestration after evidence collection, reasoning, and verification-check suggestion.

    Flow:
        Evidence + reasoning bundle -> Report Composer -> report generators -> downloadable files/history.

    Safety:
        The report is descriptive only. It must not execute SQL or invent evidence beyond the supplied bundle.
    """

    document_titles = [doc.title for doc in bundle.documents]
    entity_rows = [{"Type": entity.entity_type, "Value": entity.value} for entity in bundle.entities]
    ranked_rows = [
        {"Object Type": item.object_type, "Name": item.name, "Score": item.score, "Reason": item.reason}
        for item in bundle.ranked_objects
    ]
    metadata_rows = [
        {
            "Object Type": "Table",
            "Name": table.name,
            "Columns": ", ".join(table.columns[:12]),
            "Indexes": ", ".join((idx.get("name") or "") for idx in (table.indexes or [])[:5]),
            "Foreign Keys": ", ".join((fk.get("referred_table") or "") for fk in (table.foreign_keys or [])[:5]),
            "Score": table.score,
        }
        for table in bundle.metadata.tables
    ]
    metadata_rows.extend({"Object Type": "View", "Name": view, "Columns": "", "Indexes": "", "Foreign Keys": "", "Score": ""} for view in bundle.metadata.views)
    metadata_rows.extend({"Object Type": "Procedure", "Name": proc, "Columns": "", "Indexes": "", "Foreign Keys": "", "Score": ""} for proc in bundle.metadata.procedures)
    proc_rows = [
        {
            "Procedure": item.name,
            "Definition": "Yes" if item.definition_available else "No",
            "Tables Read": ", ".join(item.tables_read),
            "Tables Written": ", ".join(item.tables_written),
            "Joins": item.joins,
            "INSERT": item.insert_statements,
            "UPDATE": item.update_statements,
            "DELETE": item.delete_statements,
            "MERGE": item.merge_statements,
            "Loops": item.loops,
            "Transactions": item.transactions,
            "TRY/CATCH": "Yes" if item.try_catch else "No",
            "Rollback": item.rollback_statements,
            "Cursors": item.cursors,
            "Temp Tables": item.temp_tables,
            "Dynamic SQL": "Yes" if item.dynamic_sql else "No",
            "Missing EXISTS": "Yes" if item.missing_exists_checks else "No",
            "Missing Unique Check": "Yes" if item.missing_uniqueness_checks else "No",
            "Deadlock Risk": item.deadlock_risk,
            "Complexity": item.complexity,
            "Complexity Score": item.complexity_score,
            "Locking Risk": item.locking_risk,
        }
        for item in bundle.procedure_analysis
    ]
    hypothesis_rows = [
        {
            "Hypothesis": item.hypothesis_id,
            "Description": item.description,
            "Initial Confidence": f"{int(item.initial_confidence * 100)}%",
            "Required Evidence": "; ".join(item.required_evidence),
            "Tables": ", ".join(item.tables_to_inspect),
            "Procedures": ", ".join(item.procedures_to_inspect),
            "Logs": ", ".join(item.logs_to_inspect),
        }
        for item in bundle.hypothesis_reasoning.hypotheses
    ]
    evaluation_rows = [
        {
            "Rank": index,
            "Hypothesis": item.hypothesis_id,
            "Description": item.description,
            "Confidence": f"{int(item.confidence * 100)}%",
            "Supporting Evidence": "; ".join(item.supporting_evidence),
            "Contradicting Evidence": "; ".join(item.contradicting_evidence),
            "Missing Evidence": "; ".join(item.missing_evidence),
            "Reason": item.reason,
        }
        for index, item in enumerate(bundle.hypothesis_reasoning.ranked_root_causes, start=1)
    ]
    process_rows = [
        {"From": source, "To": target}
        for source, target in bundle.hypothesis_reasoning.process_graph
    ]
    correlated_rows = [
        {
            "Type": item.evidence_type,
            "Subject": item.subject,
            "Finding": item.finding,
            "Support": item.support,
            "Confidence": item.confidence,
        }
        for item in bundle.correlated_evidence
    ]
    plan_rows = [
        {
            "Hypothesis": hypothesis.hypothesis_id,
            "Objects To Inspect": ", ".join([*hypothesis.tables_to_inspect, *hypothesis.procedures_to_inspect, *hypothesis.logs_to_inspect]),
            "Evidence Required": "; ".join(hypothesis.required_evidence),
            "SQL Focus": "; ".join(hypothesis.sql_focus),
            "Confidence Impact": "Raises confidence when returned rows or metadata support this hypothesis; lowers confidence when evidence is absent or contradictory.",
        }
        for hypothesis in bundle.hypothesis_reasoning.hypotheses
    ]
    focus = bundle.evidence_focus
    self_validation_rows = (
        [{"Question": item.split("?", 1)[0] + "?", "Answer": item.split("?", 1)[1].strip() if "?" in item else item} for item in focus.self_validation]
        if focus
        else [
            {"Question": "Did I investigate the target object?", "Answer": "Yes" if bundle.ranked_objects and bundle.evidence else "Needs more evidence"},
            {"Question": "Did I collect evidence?", "Answer": "Yes" if bundle.evidence else "No"},
            {"Question": "Does every conclusion have evidence?", "Answer": "Yes" if any(item.supporting_evidence for item in bundle.hypothesis_reasoning.ranked_root_causes) else "Needs more evidence"},
            {"Question": "Did I ignore unrelated objects?", "Answer": "Yes; objects are ranked from question, metadata, documents, and knowledge."},
            {"Question": "Could another hypothesis explain this?", "Answer": "Yes; alternatives are listed and ranked." if len(bundle.hypothesis_reasoning.ranked_root_causes) > 1 else "No strong alternative was evidenced."},
        ]
    )
    procedure_rank_rows = [
        {
            "Rank": index,
            "Procedure": item.procedure,
            "Score": item.score,
            "Writes Affected Object": "Yes" if item.writes_affected_object else "No",
            "Reads Affected Object": "Yes" if item.reads_affected_object else "No",
            "Relationship": item.relationship_to_affected_object,
            "Evidence": "; ".join(item.evidence_found),
            "Historical Incidents": "; ".join(item.historical_incidents) or "",
        }
        for index, item in enumerate((focus.ranked_procedures if focus else []), start=1)
    ]
    candidate_trace_rows = [
        {
            "Object Type": item.get("object_type", ""),
            "Name": item.get("name", ""),
            "Score": item.get("score", ""),
            "Decision": item.get("decision", ""),
            "Reason": item.get("reason", ""),
        }
        for item in (bundle.metadata.candidate_trace or [])[:30]
    ]
    fact_rows = [{"Type": "Confirmed Fact", "Finding": item} for item in (bundle.reasoning.confirmed_facts or [])]
    fact_rows.extend({"Type": "Inferred Finding", "Finding": item} for item in (bundle.reasoning.inferred_findings or []))
    fact_rows.extend({"Type": "Hypothesis", "Finding": item} for item in (bundle.reasoning.hypotheses or []))
    final_root_cause_items = bundle.reasoning.likely_root_causes or [
        f"{item.hypothesis_id} ({int(item.confidence * 100)}%): {item.description} - {item.reason}"
        for item in bundle.hypothesis_reasoning.ranked_root_causes
    ]
    confidence_items = [f"Overall confidence: {int(bundle.confidence * 100)}%"]
    confidence_items.extend(bundle.confidence_factors or ["Based on available evidence; no unsupported objects were fabricated."])
    recommended_fix_section = ReportSection(title="Recommended Fix", items=[
        "Immediate Fix: " + " ".join(bundle.recommendation.immediate_fix),
        "Permanent Fix: " + " ".join(bundle.recommendation.permanent_fix),
        "Future Improvement: " + " ".join(bundle.recommendation.future_improvement),
        f"Estimated Effort: {bundle.recommendation.estimated_effort}",
        f"Risk: {bundle.recommendation.risk}",
        f"Business Impact: {bundle.recommendation.business_impact}",
        "Monitoring: " + " ".join(bundle.recommendation.monitoring),
        "Modernization: " + " ".join(bundle.recommendation.modernization),
    ])
    sections = [
        ReportSection(title="Executive Summary", paragraphs=[bundle.reasoning.summary]),
        ReportSection(title="Question", paragraphs=[bundle.question]),
        _executive_ai_reasoning_section(bundle),
        _executive_key_findings_section(bundle),
        _executive_evidence_summary_section(bundle),
        _write_path_likely_procedure_section(bundle),
        ReportSection(title="Root Cause", items=final_root_cause_items[:3]),
        ReportSection(title="Confidence Score", items=confidence_items),
        _executive_fix_section(bundle),
        _executive_tests_section(bundle),
        ReportSection(title="Proof of Fix", items=bundle.reasoning.proof_of_fix),
        ReportSection(title="Rollback", items=bundle.reasoning.rollback_plan[:4]),
        ReportSection(title="Missing Evidence", items=bundle.reasoning.missing_evidence),
        ReportSection(title="Stage 1 - Understand the Question", items=[
            f"Investigation Mode: {bundle.investigation_mode}",
            f"Mode Rationale: {bundle.mode_rationale or 'Default full investigation path selected.'}",
            f"Investigation Goal: {bundle.intent.intent.value}",
            f"User Goal: {bundle.hypothesis_reasoning.understanding.user_goal}",
            f"Working Hypothesis: {bundle.hypothesis_reasoning.understanding.user_hypothesis}",
        ]),
        _ai_reasoning_section(bundle),
        ReportSection(title="Stage 2 - Discover Context", tables=[
            ReportTable(title="Discovered Objects", columns=["Object Type", "Name", "Columns", "Indexes", "Foreign Keys", "Score"], rows=metadata_rows),
            ReportTable(title="Procedure Analysis", columns=["Procedure", "Definition", "Tables Read", "Tables Written", "Joins", "INSERT", "UPDATE", "DELETE", "MERGE", "Loops", "Transactions", "TRY/CATCH", "Rollback", "Cursors", "Temp Tables", "Dynamic SQL", "Missing EXISTS", "Missing Unique Check", "Deadlock Risk", "Complexity", "Complexity Score", "Locking Risk"], rows=proc_rows or [{"Procedure": "None", "Definition": "No stored procedures analyzed", "Tables Read": "", "Tables Written": "", "Joins": "", "INSERT": "", "UPDATE": "", "DELETE": "", "MERGE": "", "Loops": "", "Transactions": "", "TRY/CATCH": "", "Rollback": "", "Cursors": "", "Temp Tables": "", "Dynamic SQL": "", "Missing EXISTS": "", "Missing Unique Check": "", "Deadlock Risk": "", "Complexity": "", "Complexity Score": "", "Locking Risk": ""}]),
        ]),
        ReportSection(title="Evidence-First Target Discovery", items=[
            f"Affected Object: {focus.affected_object if focus else 'Not determined'}",
            f"Affected Object Reason: {focus.affected_object_reason if focus else 'No evidence focus available'}",
            f"Inferred Business Key: {(focus.inferred_business_key if focus and focus.inferred_business_key else 'Not determined')}",
            f"Business Key Reason: {focus.business_key_reason if focus else 'No evidence focus available'}",
        ]),
        ReportSection(title="Candidate Scoring Trace", tables=[ReportTable(title="Selected and Rejected Candidates", columns=["Object Type", "Name", "Score", "Decision", "Reason"], rows=candidate_trace_rows or [{"Object Type": "table", "Name": "No candidate trace available", "Score": "", "Decision": "", "Reason": ""}])]),
        ReportSection(title="Write Path Ranking", tables=[ReportTable(title="Ranked Procedures", columns=["Rank", "Procedure", "Score", "Writes Affected Object", "Reads Affected Object", "Relationship", "Evidence", "Historical Incidents"], rows=procedure_rank_rows or [{"Rank": "", "Procedure": "No write path confirmed", "Score": "", "Writes Affected Object": "", "Reads Affected Object": "", "Relationship": "", "Evidence": "", "Historical Incidents": ""}])]),
        ReportSection(title="Facts, Inferences, and Hypotheses", tables=[ReportTable(title="Reasoning Separation", columns=["Type", "Finding"], rows=fact_rows or [{"Type": "None", "Finding": "No evidence-backed facts or hypotheses were generated"}])]),
        ReportSection(title="Stage 3 - Generate Investigation Hypotheses", tables=[ReportTable(title="Hypotheses", columns=["Hypothesis", "Description", "Initial Confidence", "Required Evidence", "Tables", "Procedures", "Logs"], rows=hypothesis_rows)]),
        ReportSection(title="Stage 4 - Plan Investigation", tables=[ReportTable(title="Investigation Plan", columns=["Hypothesis", "Objects To Inspect", "Evidence Required", "SQL Focus", "Confidence Impact"], rows=plan_rows)]),
        ReportSection(title="Stage 5 - Collect Evidence", tables=_evidence_tables(bundle)),
        _evidence_gate_section(bundle),
        _suggested_verification_section(bundle),
        _verification_section(bundle),
        ReportSection(title="Stage 6 - Reason", tables=[ReportTable(title="Ranked Hypotheses", columns=["Rank", "Hypothesis", "Description", "Confidence", "Supporting Evidence", "Contradicting Evidence", "Missing Evidence", "Reason"], rows=evaluation_rows)]),
        ReportSection(title="Stage 7 - Generate Dynamic Report", items=["This report was generated after context discovery, hypothesis generation, evidence planning, evidence collection, reasoning, and self-validation."]),
        ReportSection(title="Self Validation", tables=[ReportTable(title="Validation Checks", columns=["Question", "Answer"], rows=self_validation_rows)]),
        ReportSection(title="Detected Intent", items=[f"Intent: {bundle.intent.intent.value}", f"Confidence: {int(bundle.intent.confidence * 100)}%", f"Rationale: {bundle.intent.rationale}"]),
        ReportSection(title="Extracted Entities", tables=[ReportTable(title="Entities", columns=["Type", "Value"], rows=entity_rows or [{"Type": "None", "Value": "No explicit entities extracted"}])]),
        ReportSection(title="Question Understanding", items=[
            f"User Goal: {bundle.hypothesis_reasoning.understanding.user_goal}",
            f"User Hypothesis: {bundle.hypothesis_reasoning.understanding.user_hypothesis}",
            f"Business Process: {bundle.hypothesis_reasoning.understanding.business_process}",
            "Likely Objects: " + (", ".join(bundle.hypothesis_reasoning.understanding.likely_objects) or "None ranked"),
            "Required Evidence: " + "; ".join(bundle.hypothesis_reasoning.understanding.required_evidence),
        ]),
        ReportSection(title="Generated Investigation Hypotheses", tables=[ReportTable(title="Hypotheses", columns=["Hypothesis", "Description", "Initial Confidence", "Required Evidence", "Tables", "Procedures", "Logs"], rows=hypothesis_rows)]),
        ReportSection(title="Relevant Object Ranking", tables=[ReportTable(title="Ranked Objects", columns=["Object Type", "Name", "Score", "Reason"], rows=ranked_rows or [{"Object Type": "None", "Name": "No ranked objects", "Score": "", "Reason": ""}])]),
        ReportSection(title="Investigation Scope", tables=[ReportTable(title="Discovered Objects", columns=["Object Type", "Name", "Columns", "Indexes", "Foreign Keys", "Score"], rows=metadata_rows)]),
        ReportSection(title="Stored Procedure Intelligence", tables=[ReportTable(title="Procedure Analysis", columns=["Procedure", "Definition", "Tables Read", "Tables Written", "Joins", "INSERT", "UPDATE", "DELETE", "MERGE", "Loops", "Transactions", "TRY/CATCH", "Rollback", "Cursors", "Temp Tables", "Dynamic SQL", "Missing EXISTS", "Missing Unique Check", "Deadlock Risk", "Complexity", "Complexity Score", "Locking Risk"], rows=proc_rows or [{"Procedure": "None", "Definition": "No stored procedures analyzed", "Tables Read": "", "Tables Written": "", "Joins": "", "INSERT": "", "UPDATE": "", "DELETE": "", "MERGE": "", "Loops": "", "Transactions": "", "TRY/CATCH": "", "Rollback": "", "Cursors": "", "Temp Tables": "", "Dynamic SQL": "", "Missing EXISTS": "", "Missing Unique Check": "", "Deadlock Risk": "", "Complexity": "", "Complexity Score": "", "Locking Risk": ""}])]),
        ReportSection(title="Evidence Collected", tables=_evidence_tables(bundle)),
        *_missing_record_sections(bundle),
        ReportSection(title="Evidence Correlation", tables=[ReportTable(title="Correlated Evidence", columns=["Type", "Subject", "Finding", "Support", "Confidence"], rows=correlated_rows or [{"Type": "None", "Subject": "", "Finding": "No correlated evidence", "Support": "", "Confidence": ""}])]),
        ReportSection(title="Diagnostic Hypothesis Evaluation", paragraphs=["Diagnostic only. Final root-cause ranking below is driven by evidence-first affected-object and write-path analysis."], tables=[ReportTable(title="Ranked Hypotheses", columns=["Rank", "Hypothesis", "Description", "Confidence", "Supporting Evidence", "Contradicting Evidence", "Missing Evidence", "Reason"], rows=evaluation_rows)]),
        ReportSection(title="Why It Happened", items=bundle.hypothesis_reasoning.event_chain),
        ReportSection(title="Business Process Graph", paragraphs=["Execution-order graph inferred from stored procedure read/write metadata only."], tables=[ReportTable(title="Inferred Execution Graph", columns=["From", "To"], rows=process_rows or [{"From": "Unable to infer", "To": "Additional procedure read/write evidence required"}])]),
        *_intent_sections(bundle),
        ReportSection(title="Recommended Investigation SQL", sql_blocks=_sql_blocks(bundle)),
        ReportSection(title="Risks", items=bundle.reasoning.risks),
        ReportSection(title="References Used", items=["Tables: " + ", ".join(table.name for table in bundle.metadata.tables[:8]), "Procedures: " + (", ".join(bundle.metadata.procedures) or "None discovered"), "Views: " + (", ".join(bundle.metadata.views) or "None discovered"), "Documents: " + (", ".join(document_titles) or "No uploaded documents found")]),
        ReportSection(title="Missing Information / Clarifying Questions", items=bundle.reasoning.missing_evidence),
    ]
    return InvestigationReport(
        cover=ReportCover(
            title="Enterprise Investigation Report",
            workspace=workspace_name,
            database=database_name,
            generated_by=generated_by,
            generated_on=now_label(),
            investigation_id=new_investigation_id(),
            report_version=REPORT_VERSION,
        ),
        executive_summary=ExecutiveSummary(
            issue_title=bundle.question[:96],
            issue_description=bundle.question,
            severity="Medium",
            business_impact="Based on available evidence, business impact should be confirmed against affected process owners and returned database rows.",
            confidence_score=int(bundle.confidence * 100),
            estimated_root_cause=final_root_cause_items[0],
            recommendation_summary=bundle.reasoning.recommended_fix[0],
            status="Investigation Complete",
        ),
        sections=sections,
    )
