from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from legacydb_copilot.databases import DatabaseEngine, default_connector_registry
from legacydb_copilot.config import Settings
from legacydb_copilot.db.connector import (
    DatabaseConnectionError,
    get_connection_pool,
)
from legacydb_copilot.dependencies import assert_same_organization, require_permission
from legacydb_copilot.db.models import DatabaseConnectionModel, WorkspaceMembershipModel
from legacydb_copilot.db.session import get_db_session
from legacydb_copilot.schemas import (
    DatabaseConnectionCreate,
    DatabaseConnectionRead,
    DatabaseConnectionUpdate,
)
from legacydb_copilot.security.access_control import (
    require_resource_owner_workspace,
    require_workspace_access,
)
from legacydb_copilot.services.audit_service import record_audit_event
from legacydb_copilot.services.secrets_service import get_secret_store

router = APIRouter(prefix="/databases", tags=["databases"])


def _looks_like_connection_string(value: str) -> bool:
    return value.startswith(
        (
            "mysql://",
            "mysql+pymysql://",
            "postgresql://",
            "postgresql+psycopg://",
            "mssql+pyodbc://",
            "sqlite://",
        )
    )


def _build_connection_string(connection: DatabaseConnectionModel) -> str:
    """Build SQLAlchemy connection string from model data."""
    secret_value = get_secret_store().get_secret(connection.secret_ref)
    if _looks_like_connection_string(secret_value):
        return secret_value

    engine = connection.engine
    host = connection.host
    port = connection.port or (3306 if engine == "mysql" else 5432)
    database = connection.database_name
    # secret_ref contains the password (or user@password format)
    secret = secret_value

    if engine == "mysql":
        return f"mysql+pymysql://{secret}@{host}:{port}/{database}"
    elif engine == "postgresql":
        return f"postgresql+psycopg://{secret}@{host}:{port}/{database}"
    elif engine == "sql_server":
        # Assuming secret is in format user:password
        return f"mssql+pyodbc://{secret}@{host}:{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
    elif engine == "sqlite":
        return f"sqlite:///{database}"
    else:
        raise ValueError(f"Unsupported database engine: {engine}")


def _store_or_keep_secret_reference(
    *,
    secret_ref: str,
    connection_string: str | None,
    name: str,
) -> str:
    reference = secret_ref.strip()
    if reference:
        return reference
    if connection_string and connection_string.strip():
        try:
            return get_secret_store().store_secret(name=name, value=connection_string.strip())
        except RuntimeError as exc:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{exc}. Use a configured reference such as keyvault://secret-name "
                    "or env://TARGET_DATABASE_URL."
                ),
            ) from exc
    raise HTTPException(status_code=422, detail="Secret reference or connection string is required")


@router.get("/engines")
def list_database_engines() -> dict[str, list[str]]:
    registry = default_connector_registry()
    return {"engines": [engine.value for engine in registry.list_engines()]}


@router.post("/connections", response_model=DatabaseConnectionRead, status_code=status.HTTP_201_CREATED)
def create_database_connection(
    payload: DatabaseConnectionCreate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("database:manage")),
) -> DatabaseConnectionModel:
    assert_same_organization(current_user, payload.organization_id)
    require_workspace_access(db, current_user, payload.workspace_id, action="database")
    data = payload.model_dump(exclude={"connection_string"})
    data["secret_ref"] = _store_or_keep_secret_reference(
        secret_ref=payload.secret_ref,
        connection_string=payload.connection_string,
        name=f"{payload.organization_id}-{payload.workspace_id}-{payload.name}",
    )
    connection = DatabaseConnectionModel(**data)
    db.add(connection)
    try:
        db.flush()
        record_audit_event(
            db,
            organization_id=connection.organization_id,
            workspace_id=connection.workspace_id,
            user_id=current_user.id,
            action="database_connection.create",
            resource_type="database_connection",
            resource_id=connection.id,
            metadata={"engine": connection.engine, "name": connection.name},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Database connection could not be created") from exc
    db.refresh(connection)
    return connection


@router.get("/connections", response_model=list[DatabaseConnectionRead])
def list_database_connections(
    organization_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("database:read")),
    workspace_id: str | None = None,
) -> list[DatabaseConnectionModel]:
    assert_same_organization(current_user, organization_id)
    query = db.query(DatabaseConnectionModel).filter(
        DatabaseConnectionModel.organization_id == organization_id
    )
    if workspace_id:
        require_workspace_access(db, current_user, workspace_id, action="read")
        query = query.filter(DatabaseConnectionModel.workspace_id == workspace_id)
    elif Settings.from_env().feature_enterprise_rbac_enabled:
        workspace_ids = [
            item.workspace_id
            for item in db.query(WorkspaceMembershipModel.workspace_id)
            .filter(
                WorkspaceMembershipModel.user_id == current_user.id,
                WorkspaceMembershipModel.is_active.is_(True),
            )
            .all()
        ]
        query = query.filter(DatabaseConnectionModel.workspace_id.in_(workspace_ids or [""]))
    return list(query.order_by(DatabaseConnectionModel.name).all())


@router.patch("/connections/{connection_id}", response_model=DatabaseConnectionRead)
def update_database_connection(
    connection_id: str,
    payload: DatabaseConnectionUpdate,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("database:manage")),
) -> DatabaseConnectionModel:
    connection = db.get(DatabaseConnectionModel, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    require_resource_owner_workspace(db, current_user, connection, action="database")
    data = payload.model_dump(exclude_unset=True)
    connection_string = data.pop("connection_string", None)
    if connection_string:
        connection.secret_ref = _store_or_keep_secret_reference(
            secret_ref="",
            connection_string=connection_string,
            name=f"{connection.organization_id}-{connection.workspace_id}-{connection.name}",
        )
    for field, value in data.items():
        setattr(connection, field, value)
    try:
        record_audit_event(
            db,
            organization_id=connection.organization_id,
            workspace_id=connection.workspace_id,
            user_id=current_user.id,
            action="database_connection.update",
            resource_type="database_connection",
            resource_id=connection.id,
            metadata={"fields": sorted([*data.keys(), *(["connection_string"] if connection_string else [])])},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Database connection could not be updated") from exc
    get_connection_pool().close(connection_id)
    db.refresh(connection)
    return connection


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_database_connection(
    connection_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("database:manage")),
) -> None:
    connection = db.get(DatabaseConnectionModel, connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    require_resource_owner_workspace(db, current_user, connection, action="database")
    connection.is_active = False
    record_audit_event(
        db,
        organization_id=connection.organization_id,
        workspace_id=connection.workspace_id,
        user_id=current_user.id,
        action="database_connection.delete",
        resource_type="database_connection",
        resource_id=connection.id,
    )
    db.commit()
    get_connection_pool().close(connection_id)


@router.post("/connections/{connection_id}/test")
def test_database_connection(
    connection_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("database:read")),
) -> dict[str, Any]:
    """Test if a database connection is valid."""
    connection_model = db.get(DatabaseConnectionModel, connection_id)
    if connection_model is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    require_resource_owner_workspace(db, current_user, connection_model, action="database")

    try:
        conn_string = _build_connection_string(connection_model)
        pool = get_connection_pool()
        connector = pool.get_or_create(connection_id, DatabaseEngine(connection_model.engine), conn_string)
        connector.connect()

        return {
            "connection_id": connection_id,
            "is_valid": True,
            "message": "Connection successful",
        }
    except Exception as exc:
        return {
            "connection_id": connection_id,
            "is_valid": False,
            "message": f"Connection error: {str(exc)}",
        }


@router.get("/connections/{connection_id}/schema")
def get_database_schema(
    connection_id: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("database:read")),
) -> dict[str, Any]:
    """Get schema metadata from the database."""
    connection_model = db.get(DatabaseConnectionModel, connection_id)
    if connection_model is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    require_resource_owner_workspace(db, current_user, connection_model, action="read")

    try:
        conn_string = _build_connection_string(connection_model)
        pool = get_connection_pool()
        connector = pool.get_or_create(connection_id, DatabaseEngine(connection_model.engine), conn_string)
        metadata = connector.get_schema_metadata()

        return metadata.to_dict()
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/connections/{connection_id}/table/{table_name}")
def get_table_schema(
    connection_id: str,
    table_name: str,
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("database:read")),
) -> dict[str, Any]:
    """Get detailed schema for a specific table."""
    connection_model = db.get(DatabaseConnectionModel, connection_id)
    if connection_model is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    require_resource_owner_workspace(db, current_user, connection_model, action="read")

    try:
        conn_string = _build_connection_string(connection_model)
        pool = get_connection_pool()
        connector = pool.get_or_create(connection_id, DatabaseEngine(connection_model.engine), conn_string)
        schema = connector.get_table_schema(table_name)

        return schema
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/connections/{connection_id}/query")
def execute_query(
    connection_id: str,
    payload: dict[str, Any],
    db: Annotated[Session, Depends(get_db_session)],
    current_user=Depends(require_permission("database:read")),
) -> dict[str, Any]:
    """Execute a SELECT query against the database."""
    connection_model = db.get(DatabaseConnectionModel, connection_id)
    if connection_model is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    require_resource_owner_workspace(db, current_user, connection_model, action="read")

    sql = payload.get("sql", "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="SQL query is required")

    try:
        conn_string = _build_connection_string(connection_model)
        pool = get_connection_pool()
        connector = pool.get_or_create(connection_id, DatabaseEngine(connection_model.engine), conn_string)
        results = connector.execute_select_query(sql)

        return {
            "connection_id": connection_id,
            "rows_returned": len(results),
            "results": results,
        }
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
