from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from evaluation.framework.contracts import ScenarioContract


class SetupFailedError(RuntimeError):
    pass


class UnsafeSQLError(RuntimeError):
    pass


class TransientAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunnerContext:
    organization_id: str
    workspace_id: str
    user_id: str
    connection_ids: dict[str, str]


@dataclass(frozen=True)
class RunnerConfig:
    api_base_url: str
    access_token: str
    context: RunnerContext
    timeout_seconds: float = 300.0
    poll_interval_seconds: float = 2.0
    max_api_retries: int = 3
    retry_backoff_seconds: float = 1.0
    concurrency: int = 1
    ai_enabled: bool = False
    database_engine: str = ""
    recovery_root: Path = Path("research/results/recovery")

    def __post_init__(self) -> None:
        if self.concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if self.timeout_seconds <= 0 or self.poll_interval_seconds < 0:
            raise ValueError("poll timing values are invalid")


@dataclass
class ExecutionResult:
    scenario_id: str
    domain: str
    status: str = "running"
    investigation_id: str = ""
    investigation_status: str = ""
    raw_request: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)
    extracted_result: dict[str, Any] = field(default_factory=dict)
    timings: dict[str, float | None] = field(default_factory=dict)
    usage_cost: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    retries: int = 0
    attempt: int = 1
    recovery_artifact: str = ""


class DatabaseLifecycle(Protocol):
    def reset(self, scenario: ScenarioContract) -> None: ...
    def inject(self, scenario: ScenarioContract) -> None: ...
    def verify(self, scenario: ScenarioContract) -> dict[str, Any]: ...
    def cleanup(self, scenario: ScenarioContract) -> None: ...


class InvestigationClient(Protocol):
    def submit(self, payload: dict[str, Any]) -> tuple[dict[str, Any], int]: ...
    def retrieve(self, investigation_id: str) -> tuple[dict[str, Any], int]: ...


class ExecutionStore(Protocol):
    def create_run(self, *, run_name: str, metadata: dict[str, Any]) -> str: ...
    def persist(self, run_id: str, scenario: ScenarioContract, result: ExecutionResult) -> None: ...
    def next_attempt(self, run_id: str, scenario_id: str) -> int: ...
    def statuses(self, run_id: str) -> list[dict[str, Any]]: ...


class InvestigationResultReader(Protocol):
    def read(
        self, investigation_id: str, *, organization_id: str, workspace_id: str
    ) -> dict[str, Any]: ...
