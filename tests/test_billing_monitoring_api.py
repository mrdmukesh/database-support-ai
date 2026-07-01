import pytest

from legacydb_copilot.api import ai_disclaimer_response, health_response
from legacydb_copilot.billing import Plan, Subscription, classify_plan_change, verify_webhook_signature
from legacydb_copilot.common import DomainError
from legacydb_copilot.monitoring import ComponentHealth, HealthSnapshot, HealthStatus


def test_plan_change_classification_and_paid_access() -> None:
    assert classify_plan_change(Plan.FREE, Plan.PROFESSIONAL) == "upgrade"
    assert classify_plan_change(Plan.ENTERPRISE, Plan.PROFESSIONAL) == "downgrade"
    assert classify_plan_change(Plan.FREE, Plan.FREE) == "no_change"
    assert Subscription(Plan.PROFESSIONAL).can_use_paid_features()
    assert not Subscription(Plan.FREE).can_use_paid_features()


def test_payment_webhook_signature_must_match() -> None:
    verify_webhook_signature("abc", "abc")

    with pytest.raises(DomainError, match="Invalid payment webhook"):
        verify_webhook_signature("bad", "abc")


def test_health_snapshot_rolls_up_component_statuses() -> None:
    assert HealthSnapshot((ComponentHealth("db", HealthStatus.OK),)).status == HealthStatus.OK
    assert (
        HealthSnapshot(
            (
                ComponentHealth("db", HealthStatus.OK),
                ComponentHealth("queue", HealthStatus.DEGRADED),
            )
        ).status
        == HealthStatus.DEGRADED
    )
    assert HealthSnapshot((ComponentHealth("db", HealthStatus.DOWN),)).status == HealthStatus.DOWN


def test_api_response_helpers_are_serializable_shapes() -> None:
    health = health_response()
    disclaimer = ai_disclaimer_response()

    assert health["status"] == HealthStatus.OK
    assert health["components"]
    assert disclaimer["disclaimer"]
