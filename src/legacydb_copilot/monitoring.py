from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from legacydb_copilot.common import utc_now


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    status: HealthStatus
    detail: str = ""


@dataclass(frozen=True)
class HealthSnapshot:
    components: tuple[ComponentHealth, ...]
    checked_at: object = field(default_factory=utc_now)

    @property
    def status(self) -> HealthStatus:
        statuses = {component.status for component in self.components}
        if HealthStatus.DOWN in statuses:
            return HealthStatus.DOWN
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.OK


@dataclass(frozen=True)
class UsageMetric:
    name: str
    value: float
    unit: str
