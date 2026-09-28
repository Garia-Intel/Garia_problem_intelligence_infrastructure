"""add persisted quality scoring"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260921_0005"
down_revision = "20260915_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quality_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("problems.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("dimension_scores", postgresql.JSONB(), nullable=False),
        sa.Column("dimension_reasons", postgresql.JSONB(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_quality_scores_problem_id", "quality_scores", ["problem_id"])
    op.create_index(
        "ix_quality_scores_methodology_version", "quality_scores", ["methodology_version"]
    )


def downgrade() -> None:
    op.drop_table("quality_scores")
