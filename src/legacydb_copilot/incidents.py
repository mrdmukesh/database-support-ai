from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from legacydb_copilot.common import DomainError, new_id, utc_now


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    FIX_VERIFIED = "fix_verified"
    MANAGER_APPROVED = "manager_approved"
    KNOWLEDGE_INDEXED = "knowledge_indexed"
    CLOSED = "closed"


@dataclass
class Incident:
    organization_id: UUID
    workspace_id: UUID
    title: str
    created_by: UUID
    id: UUID = field(default_factory=new_id)
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: object = field(default_factory=utc_now)

    def transition(self, next_status: IncidentStatus) -> None:
        allowed = {
            IncidentStatus.OPEN: {IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED},
            IncidentStatus.INVESTIGATING: {IncidentStatus.FIX_VERIFIED, IncidentStatus.CLOSED},
            IncidentStatus.FIX_VERIFIED: {IncidentStatus.MANAGER_APPROVED},
            IncidentStatus.MANAGER_APPROVED: {IncidentStatus.KNOWLEDGE_INDEXED},
            IncidentStatus.KNOWLEDGE_INDEXED: {IncidentStatus.CLOSED},
            IncidentStatus.CLOSED: set(),
        }
        if next_status not in allowed[self.status]:
            raise DomainError(f"Invalid incident transition: {self.status} -> {next_status}")
        self.status = next_status


@dataclass(frozen=True)
class KnowledgeArticle:
    incident_id: UUID
    workspace_id: UUID
    title: str
    body: str
    approved_by: UUID
    version: int = 1
    id: UUID = field(default_factory=new_id)


def create_knowledge_article(
    incident: Incident,
    *,
    title: str,
    body: str,
    approved_by: UUID,
) -> KnowledgeArticle:
    if incident.status != IncidentStatus.MANAGER_APPROVED:
        raise DomainError("Knowledge article requires verified fix and manager approval")
    if not body.strip():
        raise DomainError("Knowledge article body is required")
    article = KnowledgeArticle(
        incident_id=incident.id,
        workspace_id=incident.workspace_id,
        title=title,
        body=body,
        approved_by=approved_by,
    )
    incident.transition(IncidentStatus.KNOWLEDGE_INDEXED)
    return article
