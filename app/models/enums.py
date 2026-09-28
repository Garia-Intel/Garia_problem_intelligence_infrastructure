from enum import StrEnum


class SourceType(StrEnum):
    RESEARCH_REPORT = "research_report"
    ACADEMIC_PAPER = "academic_paper"
    GOVERNMENT_REPORT = "government_report"
    RESEARCH_PAPER = "research_paper"
    NGO_REPORT = "ngo_report"
    INTERNATIONAL_ORGANIZATION = "international_organization"
    POLICY_DOCUMENT = "policy_document"
    DATASET = "dataset"
    NEWS_ARTICLE = "news_article"
    VIDEO = "video"
    PODCAST = "podcast"
    SURVEY = "survey"
    OTHER = "other"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    FAILED = "failed"
    ARCHIVED = "archived"


class JobType(StrEnum):
    INGEST = "ingest"
    NORMALIZE = "normalize"
    EXTRACT = "extract"
    VALIDATE = "validate"
    QUALITY_SCORE = "quality_score"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProblemStatus(StrEnum):
    DRAFT = "draft"
    AI_EXTRACTED = "ai_extracted"
    QA_PENDING = "qa_pending"
    QA_FAILED = "qa_failed"
    HUMAN_REVIEW = "human_review"
    HUMAN_REVIEWED = "human_reviewed"
    VERIFICATION_REQUIRED = "verification_required"
    VERIFIED = "verified"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ProblemType(StrEnum):
    SYMPTOM = "symptom"
    STRUCTURAL = "structural"
    SYSTEMIC = "systemic"
    OPERATIONAL = "operational"
    POLICY = "policy"
    INFRASTRUCTURE = "infrastructure"
    BEHAVIORAL = "behavioral"
    UNKNOWN = "unknown"


class SystemLevel(StrEnum):
    INDIVIDUAL = "individual"
    HOUSEHOLD = "household"
    COMMUNITY = "community"
    INSTITUTIONAL = "institutional"
    NATIONAL = "national"
    REGIONAL = "regional"
    SYSTEMIC = "systemic"


class ClaimType(StrEnum):
    FACT = "fact"
    STATISTIC = "statistic"
    CAUSE = "cause"
    EFFECT = "effect"
    INTERVENTION = "intervention"
    CONTEXTUAL = "contextual"
    INTERPRETATION = "interpretation"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    PARTIALLY_VERIFIED = "partially_verified"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    REJECTED = "rejected"


class VerificationMethod(StrEnum):
    SOURCE_CHECK = "source_check"
    PRIMARY_SOURCE_CHECK = "primary_source_check"
    INDEPENDENT_CORROBORATION = "independent_corroboration"
    DATA_CHECK = "data_check"
    DOCUMENT_CHECK = "document_check"
    MANUAL_REVIEW = "manual_review"


class EvidenceType(StrEnum):
    DIRECT_QUOTE = "direct_quote"
    TABLE = "table"
    FIGURE = "figure"
    DATASET = "dataset"
    REPORTED_FINDING = "reported_finding"
    OTHER = "other"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_REVISION = "needs_revision"


class CanonicalProblemStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    MERGED = "merged"
    ARCHIVED = "archived"
    RETIRED = "retired"


class CanonicalizationDecision(StrEnum):
    CREATE_CANONICAL = "create_canonical"
    LINK_CONFIRMED = "link_confirmed"
    LINK_PROPOSED = "link_proposed"
    NOT_SAME_PROBLEM = "not_same_problem"
    RELATED_ONLY = "related_only"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CANDIDATE_REJECTED = "candidate_rejected"


class CanonicalMergeStatus(StrEnum):
    EXECUTED = "executed"
