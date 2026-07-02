from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response

from legacydb_copilot.dependencies import require_permission
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
    current_user=Depends(require_permission("chat:use")),
) -> Response:
    extension = Path(filename).suffix.lower()
    if extension not in _ALLOWED_EXTENSIONS or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="Report file not found")
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
