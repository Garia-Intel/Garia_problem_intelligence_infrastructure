"""add claim and statistic verification history"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260915_0004"
down_revision = "20260915_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "statistic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("statistics.id", ondelete="RESTRICT"),
        ),
        sa.Column("verifier_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("method", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(claim_id IS NOT NULL AND statistic_id IS NULL) OR "
            "(claim_id IS NULL AND statistic_id IS NOT NULL)",
            name="ck_verifications_exactly_one_verification_target",
        ),
    )
    op.create_index("ix_verifications_claim_id", "verifications", ["claim_id"])
    op.create_index("ix_verifications_statistic_id", "verifications", ["statistic_id"])
    op.create_index("ix_verifications_verifier_id", "verifications", ["verifier_id"])
    op.create_index("ix_verifications_status", "verifications", ["status"])


def downgrade() -> None:
    op.drop_table("verifications")
