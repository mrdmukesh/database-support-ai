from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import AuditLogModel

logger = logging.getLogger(__name__)


def record_audit_event(
    db: Session,
    *,
    organization_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    user_id: str | None = None,
    workspace_id: str | None = None,
    status: str = "success",
    metadata: dict[str, Any] | None = None,
) -> None:
    if not Settings.from_env().feature_audit_logging_enabled:
        return
    try:
        timestamp = datetime.now(UTC)
        with db.begin_nested():
            db.add(
                AuditLogModel(
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    actor_id=user_id,
                    action=action,
                    target_type=resource_type,
                    target_id=resource_id,
                    status=status,
                    metadata_json=json.dumps(metadata or {}, default=str),
                    created_at=timestamp,
                    occurred_at=timestamp,
                )
            )
    except Exception as exc:  # pragma: no cover - defensive by design
        logger.warning("Audit logging failed for action %s: %s", action, exc)
