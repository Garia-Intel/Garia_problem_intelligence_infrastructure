"""allow candidate-level canonical resolution decisions"""

import sqlalchemy as sa
from alembic import op

revision = "20260929_0008"
down_revision = "20260928_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "problem_canonicalizations",
        "canonical_problem_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_problem_canonicalizations_canonicalization_target_matches_decision",
        "problem_canonicalizations",
        "(decision = 'CANDIDATE_REJECTED' AND canonical_problem_id IS NULL) OR "
        "(decision <> 'CANDIDATE_REJECTED' AND canonical_problem_id IS NOT NULL)",
    )
    op.drop_index("uq_problem_canonicalizations_current_confirmed")
    op.create_index(
        "uq_problem_canonicalizations_current_confirmed",
        "problem_canonicalizations",
        ["problem_id"],
        unique=True,
        postgresql_where=sa.text("is_current AND decision = 'LINK_CONFIRMED'"),
    )


def downgrade() -> None:
    op.drop_index("uq_problem_canonicalizations_current_confirmed")
    op.create_index(
        "uq_problem_canonicalizations_current_confirmed",
        "problem_canonicalizations",
        ["problem_id"],
        unique=True,
        postgresql_where=sa.text("is_current AND decision = 'link_confirmed'"),
    )
    op.drop_constraint(
        "ck_problem_canonicalizations_canonicalization_target_matches_decision",
        "problem_canonicalizations",
        type_="check",
    )
    op.alter_column(
        "problem_canonicalizations",
        "canonical_problem_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
