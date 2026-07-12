from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from legacydb_copilot.routers import chat, reports
from legacydb_copilot.schemas import ChatAskRequest
from legacydb_copilot.services import investigation_reports


class LookupSession:
    def __init__(self, connections: dict[str, object]):
        self.connections = connections
        self.requested_ids: list[str] = []

    def get(self, _model, connection_id: str):
        self.requested_ids.append(connection_id)
        return self.connections.get(connection_id)


def payload(connection_id: str | None = "selected") -> ChatAskRequest:
    return ChatAskRequest(
        organization_id="org",
        workspace_id="workspace",
        connection_id=connection_id,
        user_id="user",
        question="Why?",
    )


def connection(**overrides):
    values = dict(id="selected", organization_id="org", workspace_id="workspace", is_active=True, name="Primary")
    values.update(overrides)
    return SimpleNamespace(**values)


def test_requested_connection_is_used_without_fallback() -> None:
    selected = connection()
    newest = connection(id="newest", name="Wrong database")
    db = LookupSession({"selected": selected, "newest": newest})
    assert chat._find_workspace_connection(db, payload()) is selected
    assert db.requested_ids == ["selected"]


@pytest.mark.parametrize(
    ("requested", "rows", "status", "message"),
    [
        (None, {}, 400, "required"),
        ("missing", {}, 404, "not found"),
        ("selected", {"selected": connection(is_active=False)}, 400, "inactive"),
        ("selected", {"selected": connection(workspace_id="other")}, 400, "requested workspace"),
    ],
)
def test_invalid_connections_are_rejected(requested, rows, status, message) -> None:
    with pytest.raises(HTTPException) as error:
        chat._find_workspace_connection(LookupSession(rows), payload(requested))
    assert error.value.status_code == status
    assert message in error.value.detail


def test_generated_reports_are_uploaded_and_upload_failure_is_clear(tmp_path, monkeypatch) -> None:
    report = SimpleNamespace(cover=SimpleNamespace(investigation_id="INV", title="Report"), sections=[])
    monkeypatch.setattr(investigation_reports, "report_output_dir", lambda _id: tmp_path / "reports/history/INV")
    monkeypatch.setattr(investigation_reports, "report_file_stem", lambda _report: "report_INV")
    monkeypatch.setattr(investigation_reports, "_executive_report", lambda value: value)
    for writer in ("write_html", "write_pdf", "write_docx", "write_xlsx"):
        monkeypatch.setattr(investigation_reports, writer, lambda _report, path: (path.parent.mkdir(parents=True, exist_ok=True), path.write_bytes(b"artifact")))

    saved: dict[str, bytes] = {}
    storage = SimpleNamespace(save_bytes=lambda key, content, _type=None: saved.__setitem__(key, content))
    monkeypatch.setattr(investigation_reports, "get_app_storage", lambda: storage)
    generated = investigation_reports.generate_investigation_report_files(report)
    assert len(saved) == 8
    assert set(saved) == set(investigation_reports.report_storage_references(generated).values())

    storage.save_bytes = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("blob unavailable"))
    with pytest.raises(RuntimeError, match="Report persistence failed: blob unavailable"):
        investigation_reports.generate_investigation_report_files(report)


def test_blob_download_returns_persisted_file_and_missing_is_clear(monkeypatch) -> None:
    filename = "report_INV_executive_rca.pdf"
    key = f"reports/history/INV/{filename}"
    investigation = SimpleNamespace(
        id="INV", organization_id="org", workspace_id="workspace",
        report_storage_json=json.dumps({filename: key}),
    )
    db = SimpleNamespace(get=lambda *_args: investigation, commit=lambda: None)
    monkeypatch.setattr(reports, "require_resource_owner_workspace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reports, "record_audit_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(reports.Settings, "from_env", classmethod(lambda cls: SimpleNamespace(storage_backend="azure_blob")))
    storage = SimpleNamespace(exists=lambda object_key: object_key == key, read_bytes=lambda _key: b"pdf bytes")
    monkeypatch.setattr(reports, "get_app_storage", lambda _settings=None: storage)
    response = reports.download_report_file("INV", filename, db, SimpleNamespace(id="user"))
    assert response.body == b"pdf bytes"

    storage.exists = lambda _key: False
    with pytest.raises(HTTPException) as error:
        reports.download_report_file("INV", filename, db, SimpleNamespace(id="user"))
    assert error.value.status_code == 404
    assert "Blob Storage" in error.value.detail
