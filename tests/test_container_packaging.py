from pathlib import Path


def test_runtime_image_includes_evaluation_package() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY evaluation ./evaluation" in dockerfile
    assert "COPY evaluation_scenarios ./evaluation_scenarios" in dockerfile
    assert "COPY evaluation_databases ./evaluation_databases" in dockerfile
    assert "msodbcsql18" in dockerfile
    assert "mssql-tools18" in dockerfile
    assert "/opt/mssql-tools18/bin" in dockerfile
