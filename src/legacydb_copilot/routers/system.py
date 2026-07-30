from __future__ import annotations

from fastapi import APIRouter, Depends

from legacydb_copilot.ai import disclaimer_text
from legacydb_copilot.app import create_container
from legacydb_copilot.dependencies import get_current_user
from legacydb_copilot.runtime_diagnostics import effective_runtime_configuration
from legacydb_copilot.config import Settings
from legacydb_copilot.workflow.langgraph.composition import (
    get_production_langgraph_orchestrator,
    langgraph_health,
)

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, object]:
    snapshot = create_container().health()
    available = get_production_langgraph_orchestrator() is not None
    return {
        "status": snapshot.status,
        "components": [
            {"name": component.name, "status": component.status, "detail": component.detail}
            for component in snapshot.components
        ],
        "langgraph": langgraph_health(
            Settings.from_env(),
            production_dependencies_available=available,
            graph_compiles=available,
        ),
    }


@router.get("/ai/disclaimer")
def ai_disclaimer() -> dict[str, list[str]]:
    return {"disclaimer": disclaimer_text().splitlines()}


@router.get("/system/effective-runtime")
def effective_runtime(_current_user=Depends(get_current_user)) -> dict[str, object]:
    return effective_runtime_configuration("api")
