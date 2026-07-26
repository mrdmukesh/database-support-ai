"""Reserve the post-policy migration marker without inferring environment."""

revision = "0011_demo_evaluation_connection_metadata"
down_revision = "0010_connection_scan_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Environment is trusted connection metadata and must be configured
    # explicitly by an administrator or evaluation bootstrap. Never infer it
    # from workspace or connection display names.
    pass


def downgrade() -> None:
    # This migration repairs trusted operational metadata. Reverting it to
    # production would silently change runtime safety behavior, so downgrade
    # intentionally preserves the explicit evaluation classification.
    pass
