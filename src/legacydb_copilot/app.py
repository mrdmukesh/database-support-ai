from __future__ import annotations

from dataclasses import dataclass, field

from legacydb_copilot.config import Settings
from legacydb_copilot.databases import ConnectorRegistry, default_connector_registry
from legacydb_copilot.documents import UploadPolicy
from legacydb_copilot.monitoring import ComponentHealth, HealthSnapshot, HealthStatus


@dataclass
class ApplicationContainer:
    settings: Settings = field(default_factory=Settings.from_env)
    connectors: ConnectorRegistry = field(default_factory=default_connector_registry)

    @property
    def upload_policy(self) -> UploadPolicy:
        return UploadPolicy(max_size_bytes=self.settings.upload_max_size_bytes)

    def health(self) -> HealthSnapshot:
        return HealthSnapshot(
            components=(
                ComponentHealth("application", HealthStatus.OK),
                ComponentHealth("connector_registry", HealthStatus.OK),
            )
        )


def create_container(settings: Settings | None = None) -> ApplicationContainer:
    return ApplicationContainer(settings=settings or Settings.from_env())
