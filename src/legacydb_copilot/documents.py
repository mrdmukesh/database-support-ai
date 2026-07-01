from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from uuid import UUID

from legacydb_copilot.common import DomainError


class DocumentType(StrEnum):
    PDF = ".pdf"
    DOCX = ".docx"
    TXT = ".txt"
    CSV = ".csv"
    SQL = ".sql"
    MARKDOWN = ".md"
    ZIP = ".zip"


ALLOWED_EXTENSIONS = {document_type.value for document_type in DocumentType}


@dataclass(frozen=True)
class UploadPolicy:
    max_size_bytes: int = 25 * 1024 * 1024

    def validate(self, filename: str, size_bytes: int) -> None:
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise DomainError(f"Unsupported file extension: {extension or '<none>'}")
        if size_bytes <= 0:
            raise DomainError("Uploaded file must not be empty")
        if size_bytes > self.max_size_bytes:
            raise DomainError("Uploaded file exceeds maximum size")


@dataclass(frozen=True)
class DocumentVersion:
    document_id: UUID
    version: int
    filename: str
    owner_id: UUID
    workspace_id: UUID
    sha256: str
    mime_type: str


def detect_mime_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def is_duplicate(content: bytes, known_hashes: set[str]) -> bool:
    return content_sha256(content) in known_hashes
