from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from legacydb_copilot.api import create_fastapi_app


def test_fastapi_app_serves_system_routes() -> None:
    app = create_fastapi_app()
    client = TestClient(app)

    health = client.get("/health")
    disclaimer = client.get("/ai/disclaimer")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert disclaimer.status_code == 200
    assert disclaimer.json()["disclaimer"]
