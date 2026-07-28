from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class EnvironmentType(StrEnum):
    PRODUCTION = "PRODUCTION"
    TEST = "TEST"
    DEVELOPMENT = "DEVELOPMENT"
    DEMO = "DEMO"


class SafetyProfile(StrEnum):
    PRODUCTION_STRICT_READ_ONLY = "PRODUCTION_STRICT_READ_ONLY"
    NON_PRODUCTION_DEEP_READ_ONLY = "NON_PRODUCTION_DEEP_READ_ONLY"


class EnvironmentResolutionError(ValueError):
    """Raised when trusted connection metadata cannot safely resolve an environment."""


_REGISTERED_ALIASES = {
    "production": EnvironmentType.PRODUCTION,
    "test": EnvironmentType.TEST,
    "uat": EnvironmentType.DEVELOPMENT,
    "development": EnvironmentType.DEVELOPMENT,
    "evaluation": EnvironmentType.DEMO,
    "demo": EnvironmentType.DEMO,
}


def canonical_environment(value: str | None) -> EnvironmentType:
    normalized = (value or "").strip().casefold()
    try:
        return _REGISTERED_ALIASES[normalized]
    except KeyError as exc:
        if not normalized:
            raise EnvironmentResolutionError(
                "Registered connection environment metadata is missing."
            ) from exc
        raise EnvironmentResolutionError(
            f"Unsupported registered connection environment_type {value!r}."
        ) from exc


@dataclass(frozen=True)
class EnvironmentSnapshot:
    selected_connection_id: str
    selected_database_name: str
    workspace_id: str
    environment_type: EnvironmentType
    safety_profile: SafetyProfile
    environment_source: str = "Registered connection metadata"
    procedure_execution_permitted: bool = False
    data_modification_permitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnvironmentResolution:
    snapshot: EnvironmentSnapshot
    telemetry: dict[str, Any]


def resolve_environment(
    connection: Any,
    *,
    workspace_id: str,
    request_environment: str | None,
) -> EnvironmentResolution:
    registered_raw = getattr(connection, "environment_type", None)
    registered = canonical_environment(registered_raw)
    requested = canonical_environment(request_environment) if request_environment else None
    mismatch = requested is not None and requested != registered
    telemetry = {
        "request_environment": requested.value if requested else None,
        "registered_environment": registered.value,
        "resolved_environment": registered.value,
        "safety_profile": (
            SafetyProfile.PRODUCTION_STRICT_READ_ONLY.value
            if registered == EnvironmentType.PRODUCTION
            else SafetyProfile.NON_PRODUCTION_DEEP_READ_ONLY.value
        ),
        "environment_resolution_reason": "registered_connection_metadata",
        "environment_mismatch_detected": mismatch,
    }
    if mismatch:
        raise EnvironmentResolutionError(
            "Environment mismatch: the request says "
            f"{requested.value}, but registered connection metadata says {registered.value}."
        )
    safety_profile = SafetyProfile(telemetry["safety_profile"])
    return EnvironmentResolution(
        snapshot=EnvironmentSnapshot(
            selected_connection_id=str(connection.id),
            selected_database_name=str(
                getattr(connection, "database_name", None)
                or getattr(connection, "name", "")
            ),
            workspace_id=workspace_id,
            environment_type=registered,
            safety_profile=safety_profile,
            procedure_execution_permitted=registered != EnvironmentType.PRODUCTION,
        ),
        telemetry=telemetry,
    )
