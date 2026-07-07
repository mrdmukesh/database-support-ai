from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.db.models import InvestigationModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.security.access_control import require_resource_owner_workspace
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.report_generator import REPORT_HISTORY_DIR
from legacydb_copilot.services.storage_service import get_app_storage, normalize_storage_key

router = APIRouter(prefix="/reports", tags=["reports"])

_ALLOWED_EXTENSIONS = {
    ".html": "text/html",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


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
    report_path = (REPORT_HISTORY_DIR / investigation_id / filename).resolve()
    history_root = REPORT_HISTORY_DIR.resolve()
    if history_root not in report_path.parents:
        raise HTTPException(status_code=404, detail="Report file not found")
    if not report_path.exists():
        storage_key = normalize_storage_key(
            (REPORT_HISTORY_DIR / investigation_id / filename).as_posix()
        )
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
