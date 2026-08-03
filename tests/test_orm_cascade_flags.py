from __future__ import annotations

from sqlalchemy import inspect as sa_inspect

from legacydb_copilot.db.models import WorkspaceModel


def test_workspace_relationships_use_passive_deletes():
    mapper = sa_inspect(WorkspaceModel)
    rels = mapper.relationships
    assert rels["database_connections"].passive_deletes is True
    assert rels["documents"].passive_deletes is True
    assert rels["incidents"].passive_deletes is True
    assert rels["investigations"].passive_deletes is True
    assert rels["memberships"].passive_deletes is True
