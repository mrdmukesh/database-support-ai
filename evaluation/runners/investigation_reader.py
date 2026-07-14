from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from legacydb_copilot.db.models import InvestigationModel


def _json(value: str, fallback):
    try:
        return json.loads(value) if value else fallback
    except (TypeError, json.JSONDecodeError):
        return fallback


class InvestigationPersistenceReader:
    """Read persisted outputs after public API completion; never invokes reasoning code."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def read(
        self, investigation_id: str, *, organization_id: str, workspace_id: str
    ) -> dict[str, Any]:
        with self.session_factory() as db:
            record = (
                db.query(InvestigationModel)
                .filter(
                    InvestigationModel.id == investigation_id,
                    InvestigationModel.organization_id == organization_id,
                    InvestigationModel.workspace_id == workspace_id,
                )
                .one()
            )
            return {
                "identified_entities": _json(record.extracted_entities_json, []),
                "evidence": _json(record.evidence_json, []),
                "generated_sql": _json(record.sql_queries_json, []),
                "executed_sql": _json(record.sql_queries_json, []),
                "report_snapshot": _json(record.report_snapshot_json, {}),
                "debug_trace": _json(record.ai_debug_trace_json, {}),
            }
