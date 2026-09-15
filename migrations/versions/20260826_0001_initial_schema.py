"""initial core relational schema"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260826_0001"
down_revision = None
branch_labels = None
depends_on = None

source_type = sa.Enum(
    "government_report",
    "research_paper",
    "ngo_report",
    "international_organization",
    "policy_document",
    "dataset",
    "news_article",
    "video",
    "podcast",
    "survey",
    "other",
    name="sourcetype",
    native_enum=False,
)
problem_status = sa.Enum(
    "draft",
    "ai_extracted",
    "human_review",
    "human_reviewed",
    "verification_required",
    "verified",
    "published",
    "rejected",
    "archived",
    name="problemstatus",
    native_enum=False,
)
problem_type = sa.Enum(
    "symptom",
    "structural",
    "systemic",
    "operational",
    "policy",
    "infrastructure",
    "behavioral",
    "unknown",
    name="problemtype",
    native_enum=False,
)
system_level = sa.Enum(
    "individual",
    "household",
    "community",
    "institutional",
    "national",
    "regional",
    "systemic",
    name="systemlevel",
    native_enum=False,
)
claim_type = sa.Enum(
    "fact",
    "statistic",
    "cause",
    "effect",
    "intervention",
    "contextual",
    "interpretation",
    name="claimtype",
    native_enum=False,
)
verification_status = sa.Enum(
    "unverified",
    "partially_verified",
    "verified",
    "disputed",
    "rejected",
    name="verificationstatus",
    native_enum=False,
)
evidence_type = sa.Enum(
    "direct_quote",
    "table",
    "figure",
    "dataset",
    "reported_finding",
    "other",
    name="evidencetype",
    native_enum=False,
)
review_decision = sa.Enum(
    "approve", "reject", "needs_revision", name="reviewdecision", native_enum=False
)


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("publisher", sa.String(255)),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("url", sa.String(2048)),
        sa.Column("country", sa.String(100)),
        sa.Column("language", sa.String(16)),
        sa.Column("publication_date", sa.Date()),
        sa.Column("accessed_at", sa.DateTime(timezone=True)),
        sa.Column("license", sa.String(255)),
        sa.Column("reliability_score", sa.Float()),
        sa.Column("description", sa.Text()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_sources_name", "sources", ["name"])
    op.create_index("ix_sources_publisher", "sources", ["publisher"])
    op.create_index("ix_sources_source_type", "sources", ["source_type"])
    op.create_index("ix_sources_country", "sources", ["country"])
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("document_type", sa.String(100)),
        sa.Column("language", sa.String(16)),
        sa.Column("content", sa.Text()),
        sa.Column("file_url", sa.String(2048)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("page_count", sa.Integer()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source_id", "content_hash", name="uq_documents_source_content_hash"),
    )
    op.create_index("ix_documents_source_id", "documents", ["source_id"])
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.create_table(
        "problems",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("problem_id", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(512), nullable=False, unique=True),
        sa.Column("summary", sa.Text()),
        sa.Column("category", sa.String(100)),
        sa.Column("status", problem_status, nullable=False),
        sa.Column("problem_type", problem_type, nullable=False),
        sa.Column("system_level", system_level, nullable=False),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("severity_score", sa.Float()),
        sa.Column("solvability_score", sa.Float()),
        sa.Column("trend_score", sa.Float()),
        sa.Column("ai_generated", sa.Boolean(), nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    for name, column in [
        ("problem_id", "problem_id"),
        ("slug", "slug"),
        ("status", "status"),
        ("category", "category"),
        ("created_at", "created_at"),
    ]:
        op.create_index(f"ix_problems_{name}", "problems", [column])
    op.create_table(
        "claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("problems.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("claim_type", claim_type, nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
        ),
        sa.Column("page_number", sa.Integer()),
        sa.Column("section", sa.String(255)),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("verification_status", verification_status, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_claims_problem_id", "claims", ["problem_id"])
    op.create_index("ix_claims_verification_status", "claims", ["verification_status"])
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("evidence_type", evidence_type, nullable=False),
        sa.Column("excerpt", sa.Text()),
        sa.Column("page_number", sa.Integer()),
        sa.Column("section", sa.String(255)),
        sa.Column("location", sa.String(500)),
        sa.Column("evidence_strength", sa.Float()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "statistics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("problems.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "claim_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("claims.id", ondelete="RESTRICT"),
        ),
        sa.Column("indicator", sa.String(255), nullable=False),
        sa.Column("label", sa.String(500)),
        sa.Column("value_numeric", sa.Float()),
        sa.Column("value_text", sa.String(255)),
        sa.Column("unit", sa.String(64)),
        sa.Column("year", sa.Integer()),
        sa.Column("geographic_scope", sa.String(255)),
        sa.Column("methodology", sa.Text()),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer()),
        sa.Column("verification_status", verification_status, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    for column in ["problem_id", "indicator", "year", "geographic_scope"]:
        op.create_index(f"ix_statistics_{column}", "statistics", [column])
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "problem_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("problems.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.String(255), nullable=False),
        sa.Column("decision", review_decision, nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", sa.String(255)),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("old_data", postgresql.JSONB()),
        sa.Column("new_data", postgresql.JSONB()),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    for table in [
        "audit_logs",
        "reviews",
        "statistics",
        "evidence",
        "claims",
        "problems",
        "documents",
        "sources",
    ]:
        op.drop_table(table)
