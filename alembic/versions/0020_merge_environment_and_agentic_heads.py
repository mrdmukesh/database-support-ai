"""Merge authoritative environment and agentic investigation histories.

Revision ID: 0020_merge_heads
Revises: 0016_environment_snapshot, 0019_fix_readiness
"""

revision = "0020_merge_heads"
down_revision = ("0016_environment_snapshot", "0019_fix_readiness")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join the two compatible histories without changing schema or data."""


def downgrade() -> None:
    """Return to the two predecessor heads without changing schema or data."""
