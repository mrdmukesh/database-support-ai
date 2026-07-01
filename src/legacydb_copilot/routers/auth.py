from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legacydb_copilot.auth import ConsentRecord, validate_password_strength
from legacydb_copilot.common import DomainError, utc_now
from legacydb_copilot.config import Settings
from legacydb_copilot.db.models import ConsentModel, UserModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.schemas import LoginRequest, SessionRead, UserCreate, UserRead
from legacydb_copilot.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, db: Annotated[Session, Depends(get_db_session)]) -> UserModel:
    password_errors = validate_password_strength(payload.password)
    if password_errors:
        raise HTTPException(status_code=422, detail=password_errors)
    try:
        consent = ConsentRecord(
            user_id=uuid4(),
            accepted=frozenset(payload.consents),
            ip_address=payload.ip_address,
        )
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    user = UserModel(
        organization_id=payload.organization_id,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role.value,
    )
    db.add(user)
    try:
        db.flush()
        for key in consent.accepted:
            db.add(
                ConsentModel(
                    user_id=user.id,
                    consent_key=key,
                    ip_address=payload.ip_address,
                    accepted_at=utc_now(),
                )
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User already exists or organization is invalid") from exc
    db.refresh(user)
    return user


@router.post("/login", response_model=SessionRead)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db_session)]) -> dict[str, object]:
    user = (
        db.query(UserModel)
        .filter(UserModel.email == str(payload.email), UserModel.is_active.is_(True))
        .order_by(UserModel.created_at.desc())
        .first()
    )
    if user is None or user.password_hash is None or not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    settings = Settings.from_env()

    return {
        "access_token": create_access_token(
            user_id=user.id,
            organization_id=user.organization_id,
            role=user.role,
            secret=settings.jwt_secret,
            expires_minutes=settings.jwt_access_token_minutes,
        ),
        "token_type": "bearer",
        "user": user,
    }
