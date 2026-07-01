from __future__ import annotations

from fastapi import APIRouter

from legacydb_copilot.ai import disclaimer_text
from legacydb_copilot.app import create_container

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, object]:
    snapshot = create_container().health()
    return {
        "status": snapshot.status,
        "components": [
            {"name": component.name, "status": component.status, "detail": component.detail}
            for component in snapshot.components
        ],
    }


@router.get("/ai/disclaimer")
def ai_disclaimer() -> dict[str, list[str]]:
    return {"disclaimer": disclaimer_text().splitlines()}
