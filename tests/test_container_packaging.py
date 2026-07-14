from pathlib import Path


def test_runtime_image_includes_evaluation_package() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY evaluation ./evaluation" in dockerfile
