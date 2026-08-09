from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from legacydb_copilot import bootstrap_admin as module
from legacydb_copilot.auth import Role
from legacydb_copilot.db.base import Base
from legacydb_copilot.db.models import DatabaseConnectionModel, UserModel, WorkspaceModel
from legacydb_copilot.security import verify_password


def test_bootstrap_creates_only_platform_org_and_super_admin(monkeypatch, tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'bootstrap.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "Admin@Example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "StrongBootstrapPass123!")

    assert module.bootstrap_admin() is True
    assert module.bootstrap_admin() is True

    with factory() as db:
        users = db.query(UserModel).all()
        assert len(users) == 1
        assert users[0].email == "admin@example.com"
        assert users[0].role == Role.SUPER_ADMIN.value
        assert verify_password("StrongBootstrapPass123!", users[0].password_hash or "")
        assert db.query(WorkspaceModel).count() == 0
        assert db.query(DatabaseConnectionModel).count() == 0
