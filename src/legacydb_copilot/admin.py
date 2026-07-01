from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdminDashboardSummary:
    organizations: int
    users: int
    active_subscriptions: int
    documents: int
    incidents: int
    failed_logins: int
    blocked_users: int
    monthly_recurring_revenue: float

    def as_cards(self) -> dict[str, int | float]:
        return {
            "organizations": self.organizations,
            "users": self.users,
            "active_subscriptions": self.active_subscriptions,
            "documents": self.documents,
            "incidents": self.incidents,
            "failed_logins": self.failed_logins,
            "blocked_users": self.blocked_users,
            "monthly_recurring_revenue": self.monthly_recurring_revenue,
        }
