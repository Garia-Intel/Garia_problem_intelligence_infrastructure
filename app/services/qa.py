from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import NotFoundError
from app.models.claim import Claim
from app.models.document import Document
from app.models.enums import ProblemStatus
from app.models.pipeline import ExtractionRun
from app.models.problem import Problem
from app.models.qa import QAResult
from app.models.source import Source

VALIDATOR_VERSION = "v1"


def check(
    code: str,
    category: str,
    severity: str,
    passed: bool,
    message: str,
    field: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "check_code": code,
        "category": category,
        "severity": severity,
        "passed": passed,
        "message": message,
        "field": field,
        "metadata": metadata,
    }


def run_problem_qa(db: Session, problem_id: object) -> QAResult:
    problem = db.scalar(
        select(Problem)
        .options(
            selectinload(Problem.claims).selectinload(Claim.evidence_items),
            selectinload(Problem.statistics),
        )
        .where(Problem.id == problem_id)
    )
    if problem is None or problem.deleted:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Problem does not exist.")
    checks: list[dict] = []
    checks.extend(
        [
            check(
                "MISSING_REQUIRED_FIELD",
                "required_fields",
                "error",
                bool(problem.title.strip()),
                "Problem title is required.",
                "title",
            ),
            check(
                "MISSING_REQUIRED_FIELD",
                "required_fields",
                "warning",
                bool(problem.summary and problem.summary.strip()),
                "Problem summary is recommended for review.",
                "summary",
            ),
            check(
                "INVALID_CATEGORY",
                "taxonomy",
                "warning",
                problem.category is not None,
                "Category is not assigned.",
                "category",
            ),
        ]
    )
    source_ids = {claim.source_id for claim in problem.claims if claim.source_id}
    source_ids.update(
        statistic.source_id for statistic in problem.statistics if statistic.source_id
    )
    document_ids = {claim.document_id for claim in problem.claims if claim.document_id}
    document_ids.update(
        evidence.document_id
        for claim in problem.claims
        for evidence in claim.evidence_items
        if evidence.document_id
    )
    document_ids.update(
        statistic.document_id for statistic in problem.statistics if statistic.document_id
    )
    claim_ids = {claim.id for claim in problem.claims}
    evidence_ids = {evidence.id for claim in problem.claims for evidence in claim.evidence_items}
    run_ids = {
        run_id
        for run_id in [
            *(claim.extraction_run_id for claim in problem.claims),
            *(statistic.extraction_run_id for statistic in problem.statistics),
        ]
        if run_id
    }
    existing_sources = (
        set(db.scalars(select(Source.id).where(Source.id.in_(source_ids)))) if source_ids else set()
    )
    existing_documents = (
        set(db.scalars(select(Document.id).where(Document.id.in_(document_ids))))
        if document_ids
        else set()
    )
    existing_runs = (
        set(db.scalars(select(ExtractionRun.id).where(ExtractionRun.id.in_(run_ids))))
        if run_ids
        else set()
    )
    source_ids_from_claims: set[object] = set()
    for claim in problem.claims:
        source_exists = claim.source_id is not None and claim.source_id in existing_sources
        checks.append(
            check(
                "CLAIM_SOURCE_MISSING",
                "provenance",
                "error",
                source_exists,
                "Claim requires an existing source.",
                f"claims.{claim.id}.source_id",
            )
        )
        checks.append(
            check(
                "CLAIM_EVIDENCE_MISSING",
                "claims",
                "warning",
                bool(claim.evidence_items),
                "Claim has no attached evidence.",
                f"claims.{claim.id}.evidence",
            )
        )
        if claim.source_id:
            source_ids_from_claims.add(claim.source_id)
        if claim.document_id is not None:
            checks.append(
                check(
                    "CLAIM_DOCUMENT_MISSING",
                    "provenance",
                    "error",
                    claim.document_id in existing_documents,
                    "Claim references a document that does not exist.",
                    f"claims.{claim.id}.document_id",
                )
            )
        if claim.extraction_run_id is not None:
            checks.append(
                check(
                    "CLAIM_EXTRACTION_RUN_MISSING",
                    "provenance",
                    "error",
                    claim.extraction_run_id in existing_runs,
                    "Claim references an extraction run that does not exist.",
                    f"claims.{claim.id}.extraction_run_id",
                )
            )
        for evidence in claim.evidence_items:
            document_exists = evidence.document_id in existing_documents
            checks.append(
                check(
                    "EVIDENCE_DOCUMENT_MISSING",
                    "evidence",
                    "error",
                    document_exists,
                    "Evidence references a document that does not exist.",
                    f"evidence.{evidence.id}.document_id",
                )
            )
            belongs_to_claim_source = (
                claim.document_id is None or evidence.document_id == claim.document_id
            )
            checks.append(
                check(
                    "BROKEN_PROVENANCE",
                    "provenance",
                    "error",
                    belongs_to_claim_source,
                    "Evidence document conflicts with the claim document.",
                    f"evidence.{evidence.id}.document_id",
                )
            )
            checks.append(
                check(
                    "EVIDENCE_TEXT_MISSING",
                    "evidence",
                    "warning",
                    bool(evidence.excerpt and evidence.excerpt.strip()),
                    "Evidence excerpt is empty; reviewer must inspect the source location.",
                    f"evidence.{evidence.id}.excerpt",
                )
            )
    checks.append(
        check(
            "SOURCE_NOT_FOUND",
            "provenance",
            "error",
            bool(source_ids_from_claims),
            "A candidate requires at least one source-linked claim.",
            "claims",
        )
    )
    seen_stats: set[tuple] = set()
    for statistic in problem.statistics:
        source_exists = statistic.source_id in existing_sources
        indicator_valid = bool(statistic.indicator and statistic.indicator.strip())
        value_valid = statistic.value_numeric is not None or bool(
            statistic.value_text and statistic.value_text.strip()
        )
        document_exists = statistic.document_id in existing_documents
        claim_exists = statistic.claim_id is None or statistic.claim_id in claim_ids
        evidence_exists = statistic.evidence_id is None or statistic.evidence_id in evidence_ids
        geography_valid = statistic.geographic_scope is None or bool(
            statistic.geographic_scope.strip()
        )
        checks.extend(
            [
                check(
                    "MISSING_STATISTIC_INDICATOR",
                    "statistics",
                    "error",
                    indicator_valid,
                    "Statistic indicator is required.",
                    f"statistics.{statistic.id}.indicator",
                ),
                check(
                    "INVALID_STATISTIC_VALUE",
                    "statistics",
                    "error",
                    value_valid,
                    "Statistic requires a numeric or textual value.",
                    f"statistics.{statistic.id}",
                ),
                check(
                    "STATISTIC_DOCUMENT_MISSING",
                    "provenance",
                    "error",
                    document_exists,
                    "Statistic requires an existing document.",
                    f"statistics.{statistic.id}.document_id",
                ),
                check(
                    "STATISTIC_CLAIM_MISSING",
                    "provenance",
                    "error",
                    claim_exists,
                    "Statistic references a claim that does not exist on this candidate.",
                    f"statistics.{statistic.id}.claim_id",
                ),
                check(
                    "STATISTIC_EVIDENCE_MISSING",
                    "provenance",
                    "error",
                    evidence_exists,
                    "Statistic references evidence that does not exist on this candidate.",
                    f"statistics.{statistic.id}.evidence_id",
                ),
                check(
                    "INVALID_GEOGRAPHY",
                    "geography",
                    "warning",
                    geography_valid,
                    "Geographic scope cannot be blank when supplied.",
                    f"statistics.{statistic.id}.geographic_scope",
                ),
            ]
        )
        checks.append(
            check(
                "STATISTIC_SOURCE_MISSING",
                "statistics",
                "error",
                source_exists,
                "Statistic requires an existing source.",
                f"statistics.{statistic.id}.source_id",
            )
        )
        checks.append(
            check(
                "STATISTIC_UNIT_MISSING",
                "statistics",
                "error",
                not (statistic.value_numeric is not None and not statistic.unit),
                "Numeric statistic requires a unit.",
                f"statistics.{statistic.id}.unit",
            )
        )
        checks.append(
            check(
                "STATISTIC_DATE_MISSING",
                "statistics",
                "warning",
                statistic.year is not None and 1900 <= statistic.year <= datetime.now().year + 1,
                "Observation year is missing.",
                f"statistics.{statistic.id}.year",
            )
        )
        if statistic.unit == "%" and statistic.value_numeric is not None:
            checks.append(
                check(
                    "INVALID_STATISTIC",
                    "statistics",
                    "error",
                    0 <= statistic.value_numeric <= 100,
                    "Percentage must be between 0 and 100.",
                    f"statistics.{statistic.id}.value_numeric",
                )
            )
        fingerprint = (
            (statistic.indicator or "").lower(),
            statistic.value_numeric,
            statistic.value_text,
            statistic.year,
            statistic.geographic_scope,
            statistic.source_id,
        )
        duplicate = fingerprint in seen_stats
        checks.append(
            check(
                "DUPLICATE_STATISTIC",
                "duplicates",
                "warning",
                not duplicate,
                "Potential duplicate statistic detected.",
                f"statistics.{statistic.id}",
            )
        )
        seen_stats.add(fingerprint)
    failures = [item for item in checks if not item["passed"]]
    errors = [item for item in failures if item["severity"] == "error"]
    passed = not errors
    score = round(100 * sum(item["passed"] for item in checks) / max(len(checks), 1), 2)
    result = QAResult(
        problem_id=problem.id,
        validator_version=VALIDATOR_VERSION,
        passed=passed,
        score=score,
        checks=checks,
    )
    db.add(result)
    if problem.status not in {ProblemStatus.VERIFIED, ProblemStatus.PUBLISHED}:
        problem.status = ProblemStatus.HUMAN_REVIEW if passed else ProblemStatus.QA_FAILED
    db.commit()
    db.refresh(result)
    return result


def latest_problem_qa(db: Session, problem_id: object) -> QAResult:
    result = db.scalar(
        select(QAResult)
        .where(QAResult.problem_id == problem_id)
        .order_by(QAResult.created_at.desc())
    )
    if result is None:
        raise NotFoundError("QA_RESULT_NOT_FOUND", "No QA result exists for this problem.")
    return result


def problem_qa_history(db: Session, problem_id: object) -> list[QAResult]:
    problem = db.get(Problem, problem_id)
    if problem is None or problem.deleted:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Problem does not exist.")
    return list(
        db.scalars(
            select(QAResult)
            .where(QAResult.problem_id == problem_id)
            .order_by(QAResult.created_at.desc(), QAResult.id.desc())
        )
    )
