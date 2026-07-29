from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    ExecutionPathTraceModel,
    InvestigationModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.execution_path_tracing_service import (
    ExecutionObservation,
    ExecutionPathTracingService,
    ExecutionSourceType,
    ExpectedPathStep,
    TraceVerificationLabel,
)

NOW = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)


def step(step_id: str, sequence: int, state: str = "Completed") -> ExpectedPathStep:
    return ExpectedPathStep(step_id, step_id.replace("_", " ").title(), sequence, state)


def observation(
    step_id: str,
    source: ExecutionSourceType,
    state: str,
    evidence_ref: str,
    minute: int,
    *,
    component: str = "",
    runtime: bool = False,
    data: bool = False,
    metadata: bool = False,
) -> ExecutionObservation:
    return ExecutionObservation(
        step_id=step_id,
        source_type=source,
        state=state,
        evidence_refs=(evidence_ref,),
        timestamp=NOW + timedelta(minutes=minute),
        component=component,
        runtime_verified=runtime,
        data_state_verified=data,
        metadata_only=metadata,
    )


def test_payroll_processing_path_identifies_missing_item_creation() -> None:
    trace = ExecutionPathTracingService().trace(
        affected_entity="EMP-1001",
        expected_steps=(
            step("employee_ready", 1, "Ready"),
            step("payroll_calculation", 2),
            step("payroll_item_created", 3),
        ),
        observations=(
            observation(
                "employee_ready",
                ExecutionSourceType.ENTITY_RECORD,
                "Ready",
                "SQL-EMPLOYEE",
                0,
                data=True,
            ),
            observation(
                "payroll_calculation",
                ExecutionSourceType.PROCEDURE,
                "Discovered",
                "PROC-CALCULATE",
                1,
                component="dbo.CalculatePayroll",
                metadata=True,
            ),
        ),
    )

    assert trace.last_successful_step == "employee_ready"
    assert trace.first_failed_or_missing_step == "payroll_calculation"
    assert trace.nodes[1].verification_label is TraceVerificationLabel.METADATA_ONLY
    assert trace.nodes[2].verification_label is TraceVerificationLabel.MISSING
    assert trace.responsible_component == ""
    assert "Runtime execution proof" in trace.remaining_gap


def test_banking_transfer_path_identifies_runtime_failed_component() -> None:
    trace = ExecutionPathTracingService().trace(
        affected_entity="TRF-3101",
        expected_steps=(
            step("transfer_accepted", 1),
            step("debit_posted", 2),
            step("credit_posted", 3),
        ),
        observations=(
            observation(
                "transfer_accepted",
                ExecutionSourceType.WORKFLOW,
                "Completed",
                "WF-1",
                0,
                runtime=True,
            ),
            observation(
                "debit_posted",
                ExecutionSourceType.STATUS_HISTORY,
                "Completed",
                "SQL-DEBIT",
                1,
                data=True,
            ),
            observation(
                "credit_posted",
                ExecutionSourceType.EXCEPTION,
                "Failed",
                "LOG-CREDIT",
                2,
                component="CreditPostingWorker",
                runtime=True,
            ),
        ),
    )

    assert trace.verified_completed_steps == ("transfer_accepted", "debit_posted")
    assert trace.last_successful_step == "debit_posted"
    assert trace.first_failed_or_missing_step == "credit_posted"
    assert trace.responsible_component == "CreditPostingWorker"


def test_shipping_workflow_path_can_be_fully_verified() -> None:
    trace = ExecutionPathTracingService().trace(
        affected_entity="SHP-5001",
        expected_steps=(
            step("booking_created", 1),
            step("label_generated", 2),
            step("shipment_dispatched", 3),
        ),
        observations=(
            observation(
                "booking_created",
                ExecutionSourceType.ENTITY_RECORD,
                "Completed",
                "SQL-BOOKING",
                0,
                data=True,
            ),
            observation(
                "label_generated",
                ExecutionSourceType.WORKFLOW,
                "Completed",
                "WF-LABEL",
                1,
                runtime=True,
            ),
            observation(
                "shipment_dispatched",
                ExecutionSourceType.JOB,
                "Completed",
                "JOB-DISPATCH",
                2,
                runtime=True,
            ),
        ),
    )

    assert trace.status == "COMPLETE"
    assert trace.first_failed_or_missing_step == ""
    assert trace.last_successful_step == "shipment_dispatched"
    assert all(edge.evidence_refs for edge in trace.edges)
    assert len(trace.report_timeline()) == 3


def test_missing_runtime_history_remains_unverified() -> None:
    trace = ExecutionPathTracingService().trace(
        affected_entity="EMP-1001",
        expected_steps=(step("payroll_job", 1),),
        observations=(
            observation(
                "payroll_job",
                ExecutionSourceType.JOB,
                "Configured",
                "META-JOB",
                0,
                metadata=True,
            ),
        ),
    )

    assert trace.nodes[0].verification_label is TraceVerificationLabel.METADATA_ONLY
    assert trace.verified_completed_steps == ()
    assert trace.first_failed_or_missing_step == "payroll_job"


def test_contradictory_timestamps_mark_first_inconsistent_step() -> None:
    trace = ExecutionPathTracingService().trace(
        affected_entity="SHP-5001",
        expected_steps=(step("created", 1), step("dispatched", 2)),
        observations=(
            observation(
                "created",
                ExecutionSourceType.STATUS_HISTORY,
                "Completed",
                "SQL-CREATED",
                5,
                data=True,
            ),
            observation(
                "dispatched",
                ExecutionSourceType.STATUS_HISTORY,
                "Completed",
                "SQL-DISPATCHED",
                1,
                data=True,
            ),
        ),
    )

    assert trace.nodes[1].verification_label is TraceVerificationLabel.CONTRADICTORY
    assert trace.nodes[1].outcome == "INCONSISTENT"
    assert trace.first_failed_or_missing_step == "dispatched"


def test_procedure_discovered_does_not_prove_execution() -> None:
    trace = ExecutionPathTracingService().trace(
        affected_entity="TRF-3101",
        expected_steps=(step("posting_procedure", 1),),
        observations=(
            observation(
                "posting_procedure",
                ExecutionSourceType.PROCEDURE,
                "Definition available",
                "PROC-1",
                0,
                component="dbo.PostTransfer",
                metadata=True,
            ),
        ),
    )

    assert trace.nodes[0].verification_label is TraceVerificationLabel.METADATA_ONLY
    assert trace.responsible_component == ""
    assert "does not prove execution" in trace.nodes[0].reason


def test_trace_persists_nodes_edges_and_summary() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        organization = OrganizationModel(name="Trace Test", slug="trace-test")
        workspace = WorkspaceModel(
            organization=organization,
            name="DemoPayrollV2",
            slug="demo-payroll-v2",
        )
        user = UserModel(
            organization=organization,
            email="trace@example.test",
            password_hash="x",
            full_name="Trace Test",
        )
        db.add_all((organization, workspace, user))
        db.flush()
        investigation = InvestigationModel(
            organization_id=organization.id,
            workspace_id=workspace.id,
            created_by_id=user.id,
            user_question="Trace missing PayrollItem",
            environment_type="DEMO",
            policy_name="evaluation_readonly",
            safety_profile="NON_PRODUCTION_DEEP_READ_ONLY",
            environment_source="Registered connection metadata",
            environment_snapshot_json="{}",
            environment_telemetry_json="{}",
        )
        db.add(investigation)
        db.flush()
        service = ExecutionPathTracingService()
        trace = service.trace(
            affected_entity="EMP-1001",
            expected_steps=(step("employee_ready", 1), step("payroll_item", 2)),
            observations=(
                observation(
                    "employee_ready",
                    ExecutionSourceType.ENTITY_RECORD,
                    "Ready",
                    "SQL-1",
                    0,
                    data=True,
                ),
            ),
        )

        row = service.persist(db, investigation=investigation, trace=trace)
        db.commit()

        persisted = db.get(ExecutionPathTraceModel, row.id)
        assert persisted is not None
        assert persisted.last_successful_step == "employee_ready"
        assert persisted.first_failed_or_missing_step == "payroll_item"
        assert json.loads(persisted.nodes_json)[0]["evidence_refs"] == ["SQL-1"]
        assert json.loads(persisted.edges_json)[0]["target_step_id"] == "payroll_item"
