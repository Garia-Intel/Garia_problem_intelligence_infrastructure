"""add ingestion and provenance pipeline"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260915_0002"
down_revision = "20260826_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("author", sa.String(255)))
    op.add_column("sources", sa.Column("content", sa.Text()))
    op.add_column("sources", sa.Column("content_hash", sa.String(64)))
    op.add_column(
        "sources",
        sa.Column("ingestion_method", sa.String(50), server_default="manual", nullable=False),
    )
    op.add_column("sources", sa.Column("copyright_status", sa.String(100)))
    op.add_column(
        "sources",
        sa.Column("processing_status", sa.String(20), server_default="pending", nullable=False),
    )
    op.create_unique_constraint("uq_sources_content_hash", "sources", ["content_hash"])
    op.create_index("ix_sources_processing_status", "sources", ["processing_status"])
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pipeline_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("model_version", sa.String(255)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "source_id", "job_type", "input_hash", name="uq_ingestion_jobs_source_job_input"
        ),
    )
    op.create_index("ix_ingestion_jobs_source_id", "ingestion_jobs", ["source_id"])
    op.create_table(
        "extraction_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("model", sa.String(255)),
        sa.Column("model_version", sa.String(255)),
        sa.Column("prompt_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("pipeline_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("token_usage", sa.Integer()),
        sa.Column("estimated_cost", sa.Float()),
        sa.Column("output_summary", postgresql.JSONB()),
        sa.Column("errors", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "source_id",
            "input_hash",
            "pipeline_version",
            name="uq_extraction_runs_source_input_pipeline",
        ),
    )
    op.create_index("ix_extraction_runs_source_id", "extraction_runs", ["source_id"])
    op.add_column("claims", sa.Column("location", sa.String(500)))
    op.add_column("claims", sa.Column("source_text_reference", sa.String(500)))
    op.add_column("claims", sa.Column("extraction_method", sa.String(50)))
    op.add_column(
        "claims",
        sa.Column(
            "extraction_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column("statistics", sa.Column("population", sa.String(255)))
    op.add_column("statistics", sa.Column("denominator", sa.String(255)))
    op.add_column(
        "statistics",
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column(
        "statistics",
        sa.Column(
            "extraction_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column("reviews", sa.Column("changes", postgresql.JSONB()))


def downgrade() -> None:
    op.drop_table("extraction_runs")
    op.drop_table("ingestion_jobs")
    for table, column in [
        ("reviews", "changes"),
        ("statistics", "extraction_run_id"),
        ("statistics", "evidence_id"),
        ("statistics", "denominator"),
        ("statistics", "population"),
        ("claims", "extraction_run_id"),
        ("claims", "extraction_method"),
        ("claims", "source_text_reference"),
        ("claims", "location"),
        ("sources", "processing_status"),
        ("sources", "copyright_status"),
        ("sources", "ingestion_method"),
        ("sources", "content_hash"),
        ("sources", "content"),
        ("sources", "author"),
    ]:
        op.drop_column(table, column)
