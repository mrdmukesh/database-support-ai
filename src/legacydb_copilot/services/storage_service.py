from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from legacydb_copilot.config import Settings


class AppStorage(Protocol):
    def save_bytes(self, key: str, content: bytes, content_type: str | None = None) -> str:
        ...

    def read_bytes(self, key: str) -> bytes:
        ...

    def exists(self, key: str) -> bool:
        ...


def normalize_storage_key(key: str) -> str:
    return key.replace("\\", "/").lstrip("/")


@dataclass(frozen=True)
class LocalStorage:
    root: Path

    def _path(self, key: str) -> Path:
        normalized = normalize_storage_key(key)
        candidate = Path(normalized)
        if candidate.is_absolute():
            return candidate.resolve()
        path = (self.root / normalized).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise ValueError("Storage key resolves outside configured storage root")
        return path

    def save_bytes(self, key: str, content: bytes, content_type: str | None = None) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return normalize_storage_key(key)

    def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class AzureBlobStorage:
    def __init__(self, connection_string: str, container_name: str) -> None:
        try:
            from azure.storage.blob import BlobServiceClient, ContentSettings
            from azure.core.exceptions import ResourceExistsError
        except ImportError as exc:
            raise RuntimeError(
                "Azure Blob storage requires the azure-storage-blob package"
            ) from exc
        self._content_settings_cls = ContentSettings
        self._container = BlobServiceClient.from_connection_string(
            connection_string
        ).get_container_client(container_name)
        try:
            self._container.create_container()
        except ResourceExistsError:
            pass

    def save_bytes(self, key: str, content: bytes, content_type: str | None = None) -> str:
        normalized = normalize_storage_key(key)
        settings = (
            self._content_settings_cls(content_type=content_type)
            if content_type
            else None
        )
        self._container.upload_blob(
            normalized,
            content,
            overwrite=True,
            content_settings=settings,
        )
        return normalized

    def read_bytes(self, key: str) -> bytes:
        return self._container.download_blob(normalize_storage_key(key)).readall()

    def exists(self, key: str) -> bool:
        return self._container.get_blob_client(normalize_storage_key(key)).exists()


def get_app_storage(settings: Settings | None = None) -> AppStorage:
    resolved = settings or Settings.from_env()
    if resolved.storage_backend == "azure_blob":
        if not resolved.azure_storage_connection_string:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING is required for azure_blob storage")
        return AzureBlobStorage(
            resolved.azure_storage_connection_string,
            resolved.azure_storage_container,
        )
    return LocalStorage(Path(resolved.local_storage_root))
