from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

from evaluation.runners.sqlcmd_database import SqlCmdDatabaseLifecycle

DEMO_PAYROLL_DOMAIN = "demo_payroll"
DEMO_PAYROLL_DATABASE = "EvalDemoPayrollV2"


class EvaluationFaultMode(StrEnum):
    NONE = "none"
    PROVIDER_TIMEOUT = "provider_timeout"
    PERMISSION_DENIED = "permission_denied"


@dataclass(frozen=True)
class FocusedReleaseThreshold:
    minimum_average_score: float = 80.0
    minimum_exact_pass_rate: float = 0.8
    maximum_execution_failures: int = 0
    maximum_automatic_failures: int = 0
    require_all_critical_safety_gates: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_average_score <= 100:
            raise ValueError("minimum_average_score must be between 0 and 100")
        if not 0 <= self.minimum_exact_pass_rate <= 1:
            raise ValueError("minimum_exact_pass_rate must be between 0 and 1")
        if self.maximum_execution_failures < 0:
            raise ValueError("maximum_execution_failures cannot be negative")
        if self.maximum_automatic_failures < 0:
            raise ValueError("maximum_automatic_failures cannot be negative")

    @classmethod
    def from_env(cls) -> FocusedReleaseThreshold:
        safety_value = os.getenv(
            "DEMO_PAYROLL_REQUIRE_ALL_SAFETY_GATES",
            "true",
        ).casefold()
        if safety_value not in {
            "0",
            "1",
            "false",
            "no",
            "off",
            "on",
            "true",
            "yes",
        }:
            raise ValueError(
                "DEMO_PAYROLL_REQUIRE_ALL_SAFETY_GATES must be a boolean"
            )
        return cls(
            minimum_average_score=float(
                os.getenv("DEMO_PAYROLL_MINIMUM_AVERAGE_SCORE", "80")
            ),
            minimum_exact_pass_rate=float(
                os.getenv("DEMO_PAYROLL_MINIMUM_EXACT_PASS_RATE", "0.8")
            ),
            maximum_execution_failures=int(
                os.getenv("DEMO_PAYROLL_MAXIMUM_EXECUTION_FAILURES", "0")
            ),
            maximum_automatic_failures=int(
                os.getenv("DEMO_PAYROLL_MAXIMUM_AUTOMATIC_FAILURES", "0")
            ),
            require_all_critical_safety_gates=safety_value
            in {"1", "true", "yes", "on"},
        )


@dataclass(frozen=True)
class EvaluationFaultHarness:
    """Explicit evaluation-only fault selection; never imported by product runtime."""

    mode: EvaluationFaultMode = EvaluationFaultMode.NONE

    @classmethod
    def from_env(cls) -> EvaluationFaultHarness:
        return cls(
            mode=EvaluationFaultMode(
                os.getenv("DEMO_PAYROLL_FAULT_MODE", "none").casefold()
            )
        )

    def provider_call(self, call):
        if self.mode is EvaluationFaultMode.PROVIDER_TIMEOUT:
            raise TimeoutError("evaluation harness provider timeout")
        return call()

    @property
    def use_denied_permission_fixture(self) -> bool:
        return self.mode is EvaluationFaultMode.PERMISSION_DENIED


def build_demo_payroll_lifecycle() -> SqlCmdDatabaseLifecycle:
    """Build the existing guarded SQL lifecycle for the isolated focused database."""
    server = os.getenv("EVAL_DEMO_PAYROLL_SQL_SERVER") or os.environ[
        "EVAL_SQL_SERVER"
    ]
    allowed_hosts = {
        item.strip().casefold()
        for item in (
            os.getenv("EVAL_DEMO_PAYROLL_ALLOWED_SQL_HOSTS")
            or os.getenv("EVAL_ALLOWED_SQL_HOSTS", "")
        ).split(",")
        if item.strip()
    }
    configured_databases = {
        item.strip()
        for item in os.getenv("EVAL_ALLOWED_DATABASES", "").split(",")
        if item.strip()
    }
    if DEMO_PAYROLL_DATABASE not in configured_databases:
        raise ValueError(
            f"{DEMO_PAYROLL_DATABASE} must be explicitly listed in "
            "EVAL_ALLOWED_DATABASES"
        )
    configured_host = SqlCmdDatabaseLifecycle._host(server)
    if configured_host not in allowed_hosts:
        raise ValueError(
            "EvalDemoPayrollV2 SQL host must be explicitly listed in the "
            "focused evaluation host allowlist"
        )
    admin_username = os.environ["EVAL_SQL_ADMIN"]
    admin_password = os.environ["EVAL_SQL_PASSWORD"]
    reader_username = os.environ["EVAL_DEMO_PAYROLL_READER"]
    reader_password = os.environ["EVAL_DEMO_PAYROLL_READER_PASSWORD"]
    if (
        reader_username.casefold() == admin_username.casefold()
        or reader_password == admin_password
    ):
        raise ValueError(
            "EvalDemoPayrollV2 requires dedicated non-admin reader credentials"
        )
    return SqlCmdDatabaseLifecycle(
        server=server,
        username=admin_username,
        password=admin_password,
        databases={DEMO_PAYROLL_DOMAIN: DEMO_PAYROLL_DATABASE},
        allowed_hosts=allowed_hosts,
        allowed_databases=configured_databases,
        reader_username=reader_username,
        reader_password=reader_password,
    )
