from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from legacydb_copilot.agents.entity_extraction_agent import extract_entities
from legacydb_copilot.agents.intent_agent import detect_intent
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import (
    InvestigationModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from legacydb_copilot.services.agentic_investigation_loop import (
    AgenticLoopLimits,
    DeterministicSQLPipeline,
    LoopAssessment,
    MultiStepAgenticInvestigationLoop,
)
from legacydb_copilot.services.investigation_state_machine import InvestigationState
from legacydb_copilot.services.metadata_search_service import (
    MetadataSearchResult,
    TableMetadata,
)
from legacydb_copilot.services.safe_investigation_planner import (
    EntityScope,
    EnvironmentPolicy,
    EvidenceRequest,
    EvidenceRequestType,
)
from legacydb_copilot.services.scan_policy_service import ScanPolicyService


class AzureContainerReadOnlyConnector:
    """Execute bounded reads inside the authorized Container App network."""

    engine_type = "sql_server"
    database_engine = "sql_server"

    def __init__(
        self,
        *,
        app_name: str,
        resource_group: str,
        revision: str,
        connection_id: str,
    ):
        self.app_name = app_name
        self.resource_group = resource_group
        self.revision = revision
        self.connection_id = connection_id

    def execute_read_only_query(self, sql: str, limit: int = 100):
        payload = base64.b64encode(
            json.dumps({"sql": sql, "limit": limit}).encode()
        ).decode()
        code = (
            "import base64,json,os;"
            "from sqlalchemy import create_engine,text;"
            "from legacydb_copilot.db.connector import DatabaseConnector;"
            "from legacydb_copilot.databases import DatabaseEngine;"
            f"p=json.loads(base64.b64decode('{payload}'));"
            "e=create_engine(os.environ['DATABASE_URL']);"
            f"r=e.connect().execute(text(\"select secret_ref from database_connections "
            f"where id='{self.connection_id}'\")).first();"
            "c=DatabaseConnector(DatabaseEngine.SQL_SERVER,r[0]);c.connect();"
            "rows=c.execute_read_only_query(p['sql'],limit=p['limit']);"
            "print('AG05_RESULT='+json.dumps(rows,default=str));c.disconnect()"
        )
        encoded = base64.b64encode(code.encode()).decode()
        remote = f"python -c exec(__import__('base64').b64decode('{encoded}'))"
        azure_cli = shutil.which("az")
        if not azure_cli:
            raise RuntimeError("Azure CLI was not found")
        completed = subprocess.run(
            [
                azure_cli,
                "containerapp",
                "exec",
                "--name",
                self.app_name,
                "--resource-group",
                self.resource_group,
                "--revision",
                self.revision,
                "--command",
                remote,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        match = re.search(r"AG05_RESULT=(\[.*\])", completed.stdout)
        if not match:
            raise RuntimeError("Azure validation returned no structured result")
        return json.loads(match.group(1))


class MissingPayrollItemAssessor:
    def __init__(self, employee_key: str):
        self.employee_key = employee_key

    def assess(self, evidence):
        entity = EvidenceRequest(
            request_type=EvidenceRequestType.ENTITY_LOOKUP,
            unresolved_question="AFFECTED_ENTITY",
            entity_scope=EntityScope.EXACT_KEY,
            entity_type="Employee",
            entity_key=self.employee_key,
            expected_information_gain=1.0,
        )
        related = EvidenceRequest(
            request_type=EvidenceRequestType.RELATED_RECORDS,
            unresolved_question="RELATIONSHIPS",
            entity_scope=EntityScope.EXACT_KEY,
            entity_type="PayrollItem",
            entity_key=self.employee_key,
            expected_information_gain=0.95,
        )
        if not evidence:
            return _assessment(entity, related)
        if len(evidence) == 1:
            return _assessment(related)
        missing = any(
            item.execution_status == "succeeded"
            and item.zero_row_result
            and item.evidence_semantics == "verified_absence"
            for item in evidence
        )
        reason = (
            "PayrollItem absence is verified for the employee, but the available database "
            "evidence does not establish why creation did not occur."
            if missing
            else "No eligible database evidence remains to establish the reported condition."
        )
        return LoopAssessment(
            candidates=(),
            gap_analysis={
                "status": "GAPS_IDENTIFIED",
                "gaps": [
                    {
                        "question_type": "FIRST_FAILED_STEP",
                        "source_type": "DATABASE",
                    }
                ],
            },
            terminal_state=InvestigationState.INSUFFICIENT_EVIDENCE,
            terminal_reason=reason,
        )


def _assessment(*requests: EvidenceRequest) -> LoopAssessment:
    return LoopAssessment(
        candidates=requests,
        gap_analysis={
            "status": "GAPS_IDENTIFIED",
            "gaps": [
                {
                    "question_type": request.unresolved_question,
                    "source_type": "DATABASE",
                }
                for request in requests
            ],
        },
    )


def _metadata() -> MetadataSearchResult:
    return MetadataSearchResult(
        tables=[
            TableMetadata(
                "dbo.Employee",
                [
                    "EmployeeId",
                    "EmployeeNumber",
                    "BusinessKey",
                    "PayrollStatus",
                    "Status",
                ],
                1.0,
                ["EmployeeId"],
                [],
                [],
            ),
            TableMetadata(
                "dbo.PayrollItem",
                [
                    "PayrollItemId",
                    "PayrollRunId",
                    "EmployeeId",
                    "BusinessKey",
                    "Status",
                    "ErrorCode",
                ],
                0.9,
                ["PayrollItemId"],
                [
                    {
                        "columns": ["EmployeeId"],
                        "referred_table": "dbo.Employee",
                        "referred_columns": ["EmployeeId"],
                    }
                ],
                [],
            ),
        ],
        views=[],
        procedures=[],
        version="live-validation",
        engine_type="sql_server",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--connection-id", required=True)
    parser.add_argument("--employee-key", default="EMP-1001")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", args.connection_id):
        raise ValueError("connection-id must be a UUID")

    question = f"Why is PayrollItem missing for employee {args.employee_key}?"
    connector = AzureContainerReadOnlyConnector(
        app_name=args.app_name,
        resource_group=args.resource_group,
        revision=args.revision,
        connection_id=args.connection_id,
    )
    scan_policy = ScanPolicyService().resolve_policy(
        environment_type="evaluation",
        max_scan_rows=1000,
        default_max_rows=100,
    )
    pipeline = DeterministicSQLPipeline(
        connector=connector,
        intent=detect_intent(question).intent,
        metadata=_metadata(),
        entities=extract_entities(question),
        provider="sql_server",
        scan_policy=scan_policy,
        workspace_id="Demo_Databases",
        connection_id=args.connection_id,
    )

    with tempfile.TemporaryDirectory(prefix="ag05-payroll-") as temp_dir:
        engine = create_engine(f"sqlite:///{Path(temp_dir) / 'timeline.db'}")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            organization = OrganizationModel(name="AG05 Live", slug="ag05-live")
            workspace = WorkspaceModel(
                organization=organization,
                name="Demo_Databases",
                slug="demo-databases",
            )
            user = UserModel(
                organization=organization,
                email="ag05-live@example.test",
                password_hash="not-used",
                full_name="AG05 Live",
            )
            db.add_all((organization, workspace, user))
            db.flush()
            investigation = InvestigationModel(
                organization_id=organization.id,
                workspace_id=workspace.id,
                connection_id=args.connection_id,
                connection_name="DemoPayrollV2",
                environment_type="evaluation",
                policy_name="evaluation_readonly",
                created_by_id=user.id,
                user_question=question,
            )
            db.add(investigation)
            db.flush()
            result = MultiStepAgenticInvestigationLoop(
                db,
                assessor=MissingPayrollItemAssessor(args.employee_key),
                pipeline=pipeline,
                policy=EnvironmentPolicy("evaluation", "evaluation_readonly"),
                limits=AgenticLoopLimits(
                    max_iterations=4,
                    max_sql_queries=4,
                    max_total_rows=20,
                    max_execution_seconds=180,
                    max_llm_calls=0,
                    max_tokens=0,
                    max_retries=1,
                ),
            ).run(investigation)
            timeline = [
                {
                    "iteration": step.iteration_number,
                    "request": json.loads(step.evidence_request_json)["request_type"],
                    "outcome": step.outcome,
                    "rows": sum(
                        len(item.get("rows", []))
                        for item in json.loads(step.evidence_json)
                    ),
                    "budget": json.loads(step.budget_json),
                }
                for step in result.steps
            ]
            print(
                json.dumps(
                    {
                        "investigation": question,
                        "environment": "evaluation",
                        "policy": "evaluation_readonly",
                        "timeline": timeline,
                        "terminal_state": result.terminal_state.value,
                        "terminal_reason": result.terminal_reason,
                    },
                    indent=2,
                )
            )
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
