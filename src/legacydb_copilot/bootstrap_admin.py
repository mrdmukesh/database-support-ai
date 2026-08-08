from __future__ import annotations

import os

from legacydb_copilot.auth import Role, validate_password_strength
from legacydb_copilot.db.models import OrganizationModel, UserModel
from legacydb_copilot.db.session import SessionLocal
from legacydb_copilot.security import hash_password


def bootstrap_admin() -> bool:
    """Create or promote the explicitly configured initial administrator.

    This deliberately creates no workspace, membership, or database connection.
    """
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    if not email and not password:
        return False
    if not email or not password:
        raise RuntimeError("BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD must be set together")
    password_errors = validate_password_strength(password)
    if password_errors:
        raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD does not meet password requirements")

    with SessionLocal() as db:
        organization = (
            db.query(OrganizationModel).filter(OrganizationModel.slug == "platform").one_or_none()
        )
        if organization is None:
            organization = OrganizationModel(name="Platform", slug="platform", is_active=True)
            db.add(organization)
            db.flush()

        user = (
            db.query(UserModel)
            .filter(UserModel.organization_id == organization.id, UserModel.email == email)
            .one_or_none()
        )
        if user is None:
            user = UserModel(
                organization_id=organization.id,
                email=email,
                password_hash=hash_password(password),
                full_name="Mukesh",
                role=Role.SUPER_ADMIN.value,
                is_active=True,
            )
            db.add(user)
        else:
            user.role = Role.SUPER_ADMIN.value
            user.is_active = True
        db.commit()
    return True


if __name__ == "__main__":
    bootstrap_admin()
