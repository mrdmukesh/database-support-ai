from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

from legacydb_copilot import __version__
from legacydb_copilot.config import Settings


def _git_commit() -> str:
    configured = os.getenv("APPLICATION_COMMIT", "").strip()
    if configured:
        return configured
    head = Path(".git/HEAD")
    if not head.is_file():
        return "unknown"
    value = head.read_text(encoding="utf-8").strip()
    if value.startswith("ref: "):
        ref = Path(".git") / value[5:]
        return ref.read_text(encoding="utf-8").strip() if ref.is_file() else "unknown"
    return value


def effective_runtime_configuration(process_name: str, *, started_at: str | None = None) -> dict[str, object]:
    settings = Settings.from_env()
    database = make_url(settings.database_url)
    return {
        "process_name": process_name,
        "process_id": os.getpid(),
        "process_start_time": started_at or datetime.now(timezone.utc).isoformat(),
        "application_version": __version__,
        "application_commit": _git_commit(),
        "ai_reasoning_enabled": settings.ai_reasoning_enabled,
        "llm_enabled": settings.llm_enabled,
        "verification_agent_enabled": settings.verification_agent_enabled,
        "ai_provider": settings.llm_provider,
        "ai_model": settings.llm_model,
        "openai_api_key_present": bool(settings.openai_api_key),
        "database_engine": database.get_backend_name(),
        "database_host": database.host or "local-file",
        "database_name": database.database or "",
        "organization_id": os.getenv("EVAL_ORGANIZATION_ID") or settings.evaluation_service_organization_id,
        "workspace_id": os.getenv("EVAL_WORKSPACE_ID") or settings.evaluation_service_workspace_id,
        "service_authentication_enabled": bool(
            (os.getenv("EVAL_SERVICE_CLIENT_ID") and os.getenv("EVAL_SERVICE_CLIENT_SECRET"))
            or (settings.evaluation_service_client_id and settings.evaluation_service_client_secret)
        ),
        "metadata_discovery_enabled": True,
        "relationship_analysis_enabled": True,
        "safe_sql_planning_enabled": True,
        "evidence_collection_enabled": True,
        "evidence_verification_enabled": settings.verification_agent_enabled,
        "report_composition_enabled": True,
    }


def write_runtime_diagnostic(process_name: str, path: str | Path, *, started_at: str) -> dict[str, object]:
    payload = effective_runtime_configuration(process_name, started_at=started_at)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("EFFECTIVE_RUNTIME_CONFIGURATION " + json.dumps(payload, sort_keys=True), flush=True)
    return payload
