from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from legacydb_copilot.auth import Role
from legacydb_copilot.common import Environment
from legacydb_copilot.config import Settings
from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.db.models import InvestigationModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.security.access_control import require_resource_owner_workspace
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.pii_masking_service import sanitize_ai_trace
from legacydb_copilot.services.report_generator import REPORT_HISTORY_DIR
from legacydb_copilot.services.storage_service import get_app_storage, normalize_storage_key

router = APIRouter(prefix="/reports", tags=["reports"])

_ALLOWED_EXTENSIONS = {
    ".html": "text/html",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/{investigation_id}/ai-debug-trace", response_model=None)
def download_ai_debug_trace(
    investigation_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("admin:read")),
) -> Response:
    """
    Owner: Mukesh Dabi
    Purpose:
        Returns a masked AI reasoning debug trace for a single investigation when explicitly enabled.

    Input:
        Investigation id, authenticated admin/developer user, and app database session.

    Output:
        Downloadable JSON containing masked prompts, evidence summary, LLM response, and citation validation.

    Called by:
        Admin/dev troubleshooting tools when AI_DEBUG_TRACE_ENABLED=true.

    Flow:
        Admin request -> feature/environment check -> workspace access check -> masked JSON artifact.

    Safety:
        Disabled by default and blocked in production. The trace stored by the LLM service is masked and must never
        expose database credentials, connection strings, secrets, or PII.
    """

    settings = Settings.from_env()
    if not settings.ai_debug_trace_enabled or settings.environment == Environment.PRODUCTION:
        raise HTTPException(status_code=404, detail="AI debug trace is not enabled")
    if current_user.role not in {Role.SUPER_ADMIN.value, Role.ORG_ADMIN.value}:
        raise HTTPException(status_code=403, detail="AI debug trace requires admin access")
    investigation = db.get(InvestigationModel, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    require_resource_owner_workspace(db, current_user, investigation, action="read")
    if not investigation.ai_debug_trace_json:
        raise HTTPException(status_code=404, detail="AI debug trace not available")
    try:
        trace = json.loads(investigation.ai_debug_trace_json)
    except json.JSONDecodeError:
        trace = {"raw_trace": investigation.ai_debug_trace_json}
    trace = sanitize_ai_trace(trace)
    record_audit_event(
        db,
        organization_id=investigation.organization_id,
        workspace_id=investigation.workspace_id,
        user_id=current_user.id,
        action="AI_DEBUG_TRACE_DOWNLOADED",
        resource_type="investigation",
        resource_id=investigation_id,
        metadata={"masked": True},
    )
    db.commit()
    return JSONResponse(
        content={
            "investigation_id": investigation_id,
            "trace": trace,
        },
        headers={"Content-Disposition": f'attachment; filename="{investigation_id}-ai-debug-trace.json"'},
    )


@router.get("/{investigation_id}/{filename}", response_model=None)
def download_report_file(
    investigation_id: str,
    filename: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("chat:use")),
) -> Response:
    """
    Owner: Mukesh Dabi
    Purpose:
        Serves generated investigation report files after validating workspace ownership.

    Input:
        Investigation id, filename, authenticated user, and app database session.

    Output:
        HTML/PDF inline response or DOCX/XLSX attachment from local history or configured app storage.

    Called by:
        Report download buttons in AI Chat, verification results, and learning history pages.

    Flow:
        User click -> report access check -> audit event -> local/blob storage lookup -> file response.

    Safety:
        Denies cross-workspace report access and restricts downloads to known report extensions.
    """

    extension = Path(filename).suffix.lower()
    if extension not in _ALLOWED_EXTENSIONS or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="Report file not found")
    investigation = db.get(InvestigationModel, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Report file not found")
    require_resource_owner_workspace(db, current_user, investigation, action="read")
    record_audit_event(
        db,
        organization_id=investigation.organization_id,
        workspace_id=investigation.workspace_id,
        user_id=current_user.id,
        action="REPORT_DOWNLOADED",
        resource_type="report",
        resource_id=investigation_id,
        metadata={"filename": filename, "extension": extension},
    )
    db.commit()
    settings = Settings.from_env()
    try:
        storage_refs = json.loads(investigation.report_storage_json or "{}")
    except (TypeError, json.JSONDecodeError):
        storage_refs = {}
    storage_key = storage_refs.get(filename) or normalize_storage_key(
        (REPORT_HISTORY_DIR / investigation_id / filename).as_posix()
    )
    if settings.storage_backend == "azure_blob":
        storage = get_app_storage(settings)
        try:
            if not storage.exists(storage_key):
                raise HTTPException(status_code=404, detail="Report file is missing from Blob Storage")
            content = storage.read_bytes(storage_key)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Report could not be retrieved from Blob Storage: {exc}") from exc
        disposition = "inline" if extension in {".html", ".pdf"} else "attachment"
        return Response(
            content,
            media_type=_ALLOWED_EXTENSIONS[extension],
            headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
        )

    report_path = (REPORT_HISTORY_DIR / investigation_id / filename).resolve()
    history_root = REPORT_HISTORY_DIR.resolve()
    if history_root not in report_path.parents:
        raise HTTPException(status_code=404, detail="Report file not found")
    if not report_path.exists():
        storage = get_app_storage()
        if not storage.exists(storage_key):
            raise HTTPException(status_code=404, detail="Report file not found")
        disposition = "inline" if extension in {".html", ".pdf"} else "attachment"
        return Response(
            storage.read_bytes(storage_key),
            media_type=_ALLOWED_EXTENSIONS[extension],
            headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
        )
    disposition = "inline" if extension in {".html", ".pdf"} else "attachment"
    return FileResponse(
        report_path,
        media_type=_ALLOWED_EXTENSIONS[extension],
        filename=filename,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
