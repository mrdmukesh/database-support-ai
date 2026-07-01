from uuid import uuid4

import pytest

from legacydb_copilot.common import DomainError
from legacydb_copilot.incidents import (
    Incident,
    IncidentStatus,
    create_knowledge_article,
)


def test_incident_workflow_enforces_approval_before_learning() -> None:
    incident = Incident(
        organization_id=uuid4(),
        workspace_id=uuid4(),
        title="Slow order processing",
        created_by=uuid4(),
    )

    with pytest.raises(DomainError, match="manager approval"):
        create_knowledge_article(
            incident,
            title="Fix order index",
            body="Add a composite index after validation.",
            approved_by=uuid4(),
        )

    incident.transition(IncidentStatus.INVESTIGATING)
    incident.transition(IncidentStatus.FIX_VERIFIED)
    incident.transition(IncidentStatus.MANAGER_APPROVED)

    article = create_knowledge_article(
        incident,
        title="Fix order index",
        body="Add a composite index after validation.",
        approved_by=uuid4(),
    )

    assert article.version == 1
    assert incident.status == IncidentStatus.KNOWLEDGE_INDEXED


def test_invalid_incident_transition_is_rejected() -> None:
    incident = Incident(
        organization_id=uuid4(),
        workspace_id=uuid4(),
        title="Deadlock",
        created_by=uuid4(),
    )

    with pytest.raises(DomainError, match="Invalid incident transition"):
        incident.transition(IncidentStatus.MANAGER_APPROVED)
