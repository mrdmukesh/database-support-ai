from __future__ import annotations

from pathlib import Path
from typing import Any

from legacydb_copilot.ai import disclaimer_text
from legacydb_copilot.app import ApplicationContainer, create_container


def _static_root() -> Path | None:
    candidates = [
        Path.cwd(),
        Path("/app"),
        Path(__file__).resolve().parents[2],
        Path(__file__).resolve().parents[3] if len(Path(__file__).resolve().parents) > 3 else Path.cwd(),
    ]
    for candidate in candidates:
        if (candidate / "app.html").exists():
            return candidate
    return None


def health_response(container: ApplicationContainer | None = None) -> dict[str, Any]:
    container = container or create_container()
    snapshot = container.health()
    return {
        "status": snapshot.status,
        "components": [
            {"name": component.name, "status": component.status, "detail": component.detail}
            for component in snapshot.components
        ],
    }


def ai_disclaimer_response() -> dict[str, Any]:
    return {"disclaimer": disclaimer_text().splitlines()}


def create_fastapi_app() -> Any:
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover - exercised only when optional API is used
        raise RuntimeError("Install the api extra to run FastAPI: pip install .[api]") from exc

    app = FastAPI(title="LegacyDB Support Copilot")
    project_root = _static_root()

    if project_root and (project_root / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(project_root / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    def _redirect_to_local_ui() -> Any:
        app_page = project_root / "app.html" if project_root else None
        if app_page and app_page.exists():
            return FileResponse(str(app_page))
        return PlainTextResponse("UI file app.html was not found in the deployed container.", status_code=500)

    @app.get("/app.html", include_in_schema=False)
    def _serve_app() -> Any:
        app_page = project_root / "app.html" if project_root else None
        if app_page and app_page.exists():
            return FileResponse(str(app_page))
        return PlainTextResponse("UI file app.html was not found in the deployed container.", status_code=500)

    @app.get("/index.html", include_in_schema=False)
    def _serve_index() -> Any:
        index_page = project_root / "index.html" if project_root else None
        if index_page and index_page.exists():
            return FileResponse(str(index_page))
        return RedirectResponse("/")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8080",
            "http://localhost:8080",
            "http://DESKTOP-SUG5C3Q:8080",
            "null",
        ],
        allow_origin_regex=r"http://(127\.0\.0\.1|localhost|DESKTOP-SUG5C3Q)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from legacydb_copilot.config import Settings
    from legacydb_copilot.db.schema import initialize_application_schema
    from legacydb_copilot.routers import (
        admin,
        auth,
        billing,
        chat,
        databases,
        documents,
        incidents,
        learning,
        organizations,
        reports,
        system,
        workspaces,
    )

    @app.on_event("startup")
    def _initialize_database_schema() -> None:
        initialize_application_schema(Settings.from_env().database_url)

    app.include_router(system.router)
    app.include_router(auth.router)
    app.include_router(organizations.router)
    app.include_router(workspaces.router)
    app.include_router(databases.router)
    app.include_router(documents.router)
    app.include_router(incidents.router)
    app.include_router(chat.router)
    app.include_router(learning.router)
    app.include_router(reports.router)
    app.include_router(billing.router)
    app.include_router(admin.router)

    return app
