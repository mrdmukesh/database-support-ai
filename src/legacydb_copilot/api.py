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


def _react_static_root() -> Path | None:
    candidates = [Path.cwd() / "frontend-react-dist", Path("/app/frontend-react-dist")]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate.resolve()
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
    react_root = _react_static_root()

    if project_root and (project_root / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(project_root / "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    def _redirect_to_local_ui() -> Any:
        if react_root:
            return RedirectResponse("/react")
        app_page = project_root / "app.html" if project_root else None
        if app_page and app_page.exists():
            return FileResponse(str(app_page))
        return PlainTextResponse("No deployed UI was found.", status_code=500)

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
        evaluation_dashboard,
        evaluation_jobs,
        help,
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
    app.include_router(evaluation_dashboard.router)
    app.include_router(evaluation_jobs.router)
    app.include_router(incidents.router)
    app.include_router(chat.router)
    app.include_router(help.router)
    app.include_router(learning.router)
    app.include_router(reports.router)
    app.include_router(billing.router)
    app.include_router(admin.router)

    if react_root:
        @app.get("/react/assets/{asset_path:path}", include_in_schema=False)
        def _serve_react_asset(asset_path: str) -> Any:
            asset = (react_root / "assets" / asset_path).resolve()
            assets_root = (react_root / "assets").resolve()
            if assets_root not in asset.parents or not asset.is_file():
                return PlainTextResponse("Asset not found", status_code=404)
            return FileResponse(
                str(asset),
                headers={"Cache-Control": "public, max-age=31536000, immutable"},
            )

        @app.get("/react", include_in_schema=False)
        @app.get("/react/{frontend_path:path}", include_in_schema=False)
        def _serve_react_spa(frontend_path: str = "") -> Any:
            return FileResponse(
                str(react_root / "index.html"),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )

    return app
