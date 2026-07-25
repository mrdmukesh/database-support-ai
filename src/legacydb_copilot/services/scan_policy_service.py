from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


EnvironmentType = Literal["production", "non_production", "evaluation", "demo", "test"]


@dataclass(frozen=True)
class ScanPolicy:
    name: str
    environment_type: str
    allow_unrestricted_read_scan: bool
    require_row_limit: bool
    max_rows: int
    require_filter_for_large_table: bool
    allow_metadata_scan: bool = True
    allow_relationship_discovery: bool = True
    configuration_valid: bool = True
    configuration_error: str = ""


@dataclass(frozen=True)
class ScanPolicyDecision:
    policy: str
    environment_type: str
    decision: Literal["allowed", "blocked"]
    reason: str
    max_rows: int
    table: str = ""
    suggested_rewrite: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScanPolicyService:
    SUPPORTED_ENVIRONMENTS = {
        "production",
        "non_production",
        "evaluation",
        "demo",
        "test",
    }
    RELAXED_ENVIRONMENTS = {"non_production", "evaluation", "demo", "test"}

    def resolve_policy(
        self,
        *,
        environment_type: str | None,
        max_scan_rows: int | None,
        default_max_rows: int,
    ) -> ScanPolicy:
        normalized = (environment_type or "production").strip().casefold()
        if normalized not in self.SUPPORTED_ENVIRONMENTS:
            return ScanPolicy(
                name="production_strict",
                environment_type="production",
                allow_unrestricted_read_scan=False,
                require_row_limit=True,
                max_rows=default_max_rows,
                require_filter_for_large_table=True,
                configuration_valid=False,
                configuration_error=(
                    f"Unsupported environment_type {environment_type!r}; "
                    "production_strict was applied."
                ),
            )
        if normalized in self.RELAXED_ENVIRONMENTS:
            configured_limit = max_scan_rows if max_scan_rows is not None else 500
            if configured_limit < 1 or configured_limit > 5000:
                return ScanPolicy(
                    name="production_strict",
                    environment_type="production",
                    allow_unrestricted_read_scan=False,
                    require_row_limit=True,
                    max_rows=default_max_rows,
                    require_filter_for_large_table=True,
                    configuration_valid=False,
                    configuration_error=(
                        f"Invalid max_scan_rows {configured_limit}; production_strict was applied."
                    ),
                )
            return ScanPolicy(
                name=f"{normalized}_readonly",
                environment_type=normalized,
                allow_unrestricted_read_scan=False,
                require_row_limit=True,
                max_rows=configured_limit,
                require_filter_for_large_table=False,
            )
        return ScanPolicy(
            name="production_strict",
            environment_type="production",
            allow_unrestricted_read_scan=False,
            require_row_limit=True,
            max_rows=default_max_rows,
            require_filter_for_large_table=True,
        )


def resolve_connection_scan_policy(connection: Any, *, default_max_rows: int) -> ScanPolicy:
    return ScanPolicyService().resolve_policy(
        environment_type=getattr(connection, "environment_type", None),
        max_scan_rows=getattr(connection, "max_scan_rows", None),
        default_max_rows=default_max_rows,
    )

