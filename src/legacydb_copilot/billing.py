from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from legacydb_copilot.common import DomainError


class Plan(StrEnum):
    FREE = "free"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


PLAN_ORDER = {Plan.FREE: 0, Plan.PROFESSIONAL: 1, Plan.ENTERPRISE: 2}


@dataclass(frozen=True)
class Subscription:
    plan: Plan
    active: bool = True
    in_trial: bool = False
    grace_period_days: int = 0

    def can_use_paid_features(self) -> bool:
        return self.active and self.plan is not Plan.FREE


def classify_plan_change(current: Plan, requested: Plan) -> str:
    if current == requested:
        return "no_change"
    if PLAN_ORDER[requested] > PLAN_ORDER[current]:
        return "upgrade"
    return "downgrade"


def verify_webhook_signature(signature: str, expected: str) -> None:
    if not signature or signature != expected:
        raise DomainError("Invalid payment webhook signature")
