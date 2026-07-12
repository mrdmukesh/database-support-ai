from pathlib import Path

import pytest


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    import legacydb_copilot.api as api_module

    dist = tmp_path / "frontend-react-dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<script type="module" src="/react/assets/app-abc123.js"></script>', encoding="utf-8")
    (dist / "assets" / "app-abc123.js").write_text("export {};", encoding="utf-8")
    monkeypatch.setattr(api_module, "_react_static_root", lambda: dist)
    monkeypatch.setattr(api_module, "_static_root", lambda: None)
    monkeypatch.setattr("legacydb_copilot.db.schema.initialize_application_schema", lambda _url: None)
    return TestClient(api_module.create_fastapi_app())


def test_react_html_and_frontend_fallback_are_no_cache(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    for path in ("/react", "/react/login", "/react/app/investigations/INV-1"):
        response = client.get(path)
        assert response.status_code == 200
        assert "no-cache" in response.headers["cache-control"]
        assert "/react/assets/app-abc123.js" in response.text


def test_hashed_react_assets_are_immutable_and_traversal_is_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.get("/react/assets/app-abc123.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert client.get("/react/assets/../index.html").status_code == 200  # normalized to SPA path, never asset traversal


def test_backend_and_report_routes_are_not_spa_fallback(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    assert client.get("/health").headers.get("content-type", "").startswith("application/json")
    assert str(client.app.url_path_for("download_report_file", investigation_id="I", filename="r.pdf")) == "/reports/I/r.pdf"
    assert str(client.app.url_path_for("login")) == "/auth/login"
    assert str(client.app.url_path_for("ask_chat_question")) == "/chat/ask"
    assert str(client.app.url_path_for("_serve_react_spa", frontend_path="app/dashboard")) == "/react/app/dashboard"
