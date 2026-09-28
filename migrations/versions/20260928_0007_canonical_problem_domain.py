"""add canonical problem domain"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260928_0007"
down_revision = "20260921_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_problems",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_id", sa.String(64), nullable=False),
        sa.Column("canonical_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(512), nullable=False),
        sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("merged_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column(
            "merged_into_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_problems.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("canonical_id"),
        sa.UniqueConstraint("canonical_key"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_canonical_problems_status", "canonical_problems", ["status"])
    op.create_index(
        "ix_canonical_problems_merged_into_id", "canonical_problems", ["merged_into_id"]
    )
    op.create_table(
        "problem_canonicalizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("problems.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "canonical_problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_problems.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(64), nullable=False),
        sa.Column("match_confidence", sa.Float()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(255)),
        sa.Column("methodology_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "supersedes_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("problem_canonicalizations.id", ondelete="RESTRICT"),
        ),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_problem_canonicalizations_problem_id", "problem_canonicalizations", ["problem_id"]
    )
    op.create_index(
        "ix_problem_canonicalizations_canonical_problem_id",
        "problem_canonicalizations",
        ["canonical_problem_id"],
    )
    op.create_index(
        "ix_problem_canonicalizations_decision", "problem_canonicalizations", ["decision"]
    )
    op.create_index(
        "ix_problem_canonicalizations_actor_id", "problem_canonicalizations", ["actor_id"]
    )
    op.create_index(
        "ix_problem_canonicalizations_supersedes_id", "problem_canonicalizations", ["supersedes_id"]
    )
    op.create_index(
        "ix_problem_canonicalizations_is_current", "problem_canonicalizations", ["is_current"]
    )
    op.create_index(
        "uq_problem_canonicalizations_current_confirmed",
        "problem_canonicalizations",
        ["problem_id"],
        unique=True,
        postgresql_where=sa.text("is_current AND decision = 'link_confirmed'"),
    )
    op.create_table(
        "canonical_problem_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "canonical_problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_problems.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "canonical_problem_id",
            "version_number",
            name="uq_canonical_problem_versions_problem_version",
        ),
    )
    op.create_index(
        "ix_canonical_problem_versions_canonical_problem_id",
        "canonical_problem_versions",
        ["canonical_problem_id"],
    )
    op.create_table(
        "canonical_problem_merges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_canonical_problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_problems.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "target_canonical_problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("canonical_problems.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("methodology_version", sa.String(64)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_canonical_problem_id <> target_canonical_problem_id",
            name="canonical_problem_merges_distinct_identities",
        ),
    )
    op.create_index(
        "ix_canonical_problem_merges_source_canonical_problem_id",
        "canonical_problem_merges",
        ["source_canonical_problem_id"],
    )
    op.create_index(
        "ix_canonical_problem_merges_target_canonical_problem_id",
        "canonical_problem_merges",
        ["target_canonical_problem_id"],
    )


def downgrade() -> None:
    op.drop_table("canonical_problem_merges")
    op.drop_table("canonical_problem_versions")
    op.drop_table("problem_canonicalizations")
    op.drop_table("canonical_problems")
