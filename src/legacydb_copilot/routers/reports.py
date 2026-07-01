from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from legacydb_copilot.dependencies import require_permission
from legacydb_copilot.services.report_generator import REPORT_HISTORY_DIR

router = APIRouter(prefix="/reports", tags=["reports"])

_ALLOWED_EXTENSIONS = {
    ".html": "text/html",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/{investigation_id}/{filename}")
def download_report_file(
    investigation_id: str,
    filename: str,
    current_user=Depends(require_permission("chat:use")),
) -> FileResponse:
    extension = Path(filename).suffix.lower()
    if extension not in _ALLOWED_EXTENSIONS or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=404, detail="Report file not found")
    report_path = (REPORT_HISTORY_DIR / investigation_id / filename).resolve()
    history_root = REPORT_HISTORY_DIR.resolve()
    if history_root not in report_path.parents:
        raise HTTPException(status_code=404, detail="Report file not found")
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    disposition = "inline" if extension in {".html", ".pdf"} else "attachment"
    return FileResponse(
        report_path,
        media_type=_ALLOWED_EXTENSIONS[extension],
        filename=filename,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
