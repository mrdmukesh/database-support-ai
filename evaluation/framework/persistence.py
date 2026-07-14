from __future__ import annotations

import json
from dataclasses import asdict

from sqlalchemy.orm import Session

from evaluation.framework.contracts import InvestigationResultSnapshotContract
from evaluation.framework.models import EvaluationInvestigationResultModel


def persist_investigation_result(
    db: Session,
    *,
    evaluation_run_id: str,
    test_scenario_id: str,
    snapshot: InvestigationResultSnapshotContract,
) -> EvaluationInvestigationResultModel:
    record = EvaluationInvestigationResultModel(
        evaluation_run_id=evaluation_run_id,
        test_scenario_id=test_scenario_id,
        investigation_id=snapshot.investigation_id,
        response_type=snapshot.response_type.value,
        answer=snapshot.answer,
        snapshot_json=json.dumps(asdict(snapshot), default=str, sort_keys=True),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
