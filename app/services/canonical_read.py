import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.audit import AuditLog
from app.models.canonical import (
    CanonicalProblem,
    CanonicalProblemMerge,
    CanonicalProblemVersion,
    ProblemCanonicalization,
)
from app.models.claim import Claim
from app.models.document import Document
from app.models.enums import CanonicalizationDecision, CanonicalProblemStatus
from app.models.evidence import Evidence
from app.models.problem import Problem
from app.models.quality import QualityScore
from app.models.source import Source
from app.models.statistic import Statistic

PROVENANCE_LIMIT = 50
DETAIL_HISTORY_LIMIT = 10


def _problem(db: Session, canonical_problem_id: uuid.UUID) -> CanonicalProblem:
    problem = db.get(CanonicalProblem, canonical_problem_id)
    if problem is None:
        raise NotFoundError("CANONICAL_PROBLEM_NOT_FOUND", "Canonical problem does not exist.")
    return problem


def _mappings(
    db: Session, canonical_problem_id: uuid.UUID
) -> list[tuple[ProblemCanonicalization, Problem]]:
    return list(
        db.execute(
            select(ProblemCanonicalization, Problem)
            .join(Problem, Problem.id == ProblemCanonicalization.problem_id)
            .where(
                ProblemCanonicalization.canonical_problem_id == canonical_problem_id,
                ProblemCanonicalization.decision == CanonicalizationDecision.LINK_CONFIRMED,
                ProblemCanonicalization.is_current.is_(True),
                Problem.deleted.is_(False),
            )
            .order_by(ProblemCanonicalization.created_at.desc(), ProblemCanonicalization.id.desc())
        )
    )


def _candidate(mapping: ProblemCanonicalization, problem: Problem) -> dict[str, object]:
    return {
        "problem_id": problem.id,
        "external_problem_id": problem.problem_id,
        "title": problem.title,
        "status": problem.status.value,
        "canonicalization_id": mapping.id,
        "match_confidence": mapping.match_confidence,
        "decided_at": mapping.created_at,
    }


def list_canonical_problems(
    db: Session, page: int, page_size: int, status: CanonicalProblemStatus | None
) -> dict[str, object]:
    filters = [CanonicalProblem.status == status] if status else []
    total = db.scalar(select(func.count()).select_from(CanonicalProblem).where(*filters)) or 0
    problems = list(
        db.scalars(
            select(CanonicalProblem)
            .where(*filters)
            .order_by(CanonicalProblem.created_at.desc(), CanonicalProblem.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    ids = [problem.id for problem in problems]
    counts = (
        dict(
            db.execute(
                select(ProblemCanonicalization.canonical_problem_id, func.count())
                .where(
                    ProblemCanonicalization.canonical_problem_id.in_(ids),
                    ProblemCanonicalization.decision == CanonicalizationDecision.LINK_CONFIRMED,
                    ProblemCanonicalization.is_current.is_(True),
                )
                .group_by(ProblemCanonicalization.canonical_problem_id)
            ).all()
        )
        if ids
        else {}
    )
    return {
        "items": [
            {**_identity(problem), "current_candidate_count": counts.get(problem.id, 0)}
            for problem in problems
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _identity(problem: CanonicalProblem) -> dict[str, object]:
    return {
        "id": problem.id,
        "canonical_id": problem.canonical_id,
        "canonical_key": problem.canonical_key,
        "title": problem.title,
        "slug": problem.slug,
        "problem_statement": problem.problem_statement,
        "status": problem.status,
        "activated_at": problem.activated_at,
        "merged_at": problem.merged_at,
        "archived_at": problem.archived_at,
        "merged_into_id": problem.merged_into_id,
        "created_at": problem.created_at,
        "updated_at": problem.updated_at,
    }


def provenance(db: Session, canonical_problem_id: uuid.UUID) -> dict[str, object]:
    _problem(db, canonical_problem_id)
    mappings = _mappings(db, canonical_problem_id)
    candidates = [_candidate(mapping, problem) for mapping, problem in mappings]
    problem_ids = [problem.id for _, problem in mappings]
    claims = (
        list(
            db.scalars(
                select(Claim).where(Claim.problem_id.in_(problem_ids)).limit(PROVENANCE_LIMIT)
            )
        )
        if problem_ids
        else []
    )
    statistics = (
        list(
            db.scalars(
                select(Statistic)
                .where(Statistic.problem_id.in_(problem_ids))
                .limit(PROVENANCE_LIMIT)
            )
        )
        if problem_ids
        else []
    )
    claim_ids = [claim.id for claim in claims]
    evidence = (
        list(
            db.scalars(
                select(Evidence).where(Evidence.claim_id.in_(claim_ids)).limit(PROVENANCE_LIMIT)
            )
        )
        if claim_ids
        else []
    )
    document_ids = (
        {item.document_id for item in claims if item.document_id}
        | {item.document_id for item in statistics}
        | {item.document_id for item in evidence}
    )
    source_ids = {item.source_id for item in claims if item.source_id} | {
        item.source_id for item in statistics
    }
    documents = (
        list(
            db.scalars(
                select(Document).where(Document.id.in_(document_ids)).limit(PROVENANCE_LIMIT)
            )
        )
        if document_ids
        else []
    )
    source_ids |= {document.source_id for document in documents}
    sources = (
        list(db.scalars(select(Source).where(Source.id.in_(source_ids)).limit(PROVENANCE_LIMIT)))
        if source_ids
        else []
    )
    return {
        "candidate_count": len(candidates),
        "claim_count": len(claims),
        "statistic_count": len(statistics),
        "evidence_count": len(evidence),
        "document_count": len(documents),
        "source_count": len(sources),
        "candidates": candidates,
        "claims": [
            {
                "id": item.id,
                "kind": "claim",
                "problem_id": item.problem_id,
                "document_id": item.document_id,
                "source_id": item.source_id,
                "label": item.statement,
                "page_number": item.page_number,
            }
            for item in claims
        ],
        "statistics": [
            {
                "id": item.id,
                "kind": "statistic",
                "problem_id": item.problem_id,
                "claim_id": item.claim_id,
                "document_id": item.document_id,
                "source_id": item.source_id,
                "label": item.indicator,
                "page_number": item.page_number,
            }
            for item in statistics
        ],
        "evidence": [
            {
                "id": item.id,
                "kind": "evidence",
                "problem_id": next(
                    (claim.problem_id for claim in claims if claim.id == item.claim_id),
                    uuid.UUID(int=0),
                ),
                "claim_id": item.claim_id,
                "document_id": item.document_id,
                "label": item.excerpt,
                "page_number": item.page_number,
            }
            for item in evidence
        ],
        "documents": [
            {
                "id": item.id,
                "kind": "document",
                "problem_id": uuid.UUID(int=0),
                "source_id": item.source_id,
                "label": item.title,
            }
            for item in documents
        ],
        "sources": [
            {"id": item.id, "kind": "source", "problem_id": uuid.UUID(int=0), "label": item.name}
            for item in sources
        ],
    }


def quality(db: Session, canonical_problem_id: uuid.UUID) -> dict[str, object]:
    mappings = _mappings(db, canonical_problem_id)
    ids = [problem.id for _, problem in mappings]
    scores = (
        list(
            db.scalars(
                select(QualityScore)
                .where(QualityScore.problem_id.in_(ids))
                .order_by(QualityScore.generated_at.desc(), QualityScore.id.desc())
            )
        )
        if ids
        else []
    )
    latest: dict[uuid.UUID, QualityScore] = {}
    for score in scores:
        latest.setdefault(score.problem_id, score)
    return {
        "items": [
            {
                "problem_id": score.problem_id,
                "quality_score_id": score.id,
                "methodology_version": score.methodology_version,
                "overall_score": score.overall_score,
                "dimension_scores": score.dimension_scores,
                "generated_at": score.generated_at,
            }
            for score in latest.values()
        ]
    }


def detail(db: Session, canonical_problem_id: uuid.UUID) -> dict[str, object]:
    problem = _problem(db, canonical_problem_id)
    versions = list(
        db.scalars(
            select(CanonicalProblemVersion)
            .where(CanonicalProblemVersion.canonical_problem_id == problem.id)
            .order_by(CanonicalProblemVersion.version_number.desc())
            .limit(DETAIL_HISTORY_LIMIT)
        )
    )
    merges = list(
        db.scalars(
            select(CanonicalProblemMerge)
            .where(
                or_(
                    CanonicalProblemMerge.source_canonical_problem_id == problem.id,
                    CanonicalProblemMerge.target_canonical_problem_id == problem.id,
                )
            )
            .order_by(CanonicalProblemMerge.created_at.desc())
            .limit(DETAIL_HISTORY_LIMIT)
        )
    )
    audits = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.entity_id == problem.id)
            .order_by(AuditLog.timestamp.desc())
            .limit(DETAIL_HISTORY_LIMIT)
        )
    )
    data = _identity(problem)
    data.update(
        {
            "linked_candidates": [
                _candidate(mapping, candidate) for mapping, candidate in _mappings(db, problem.id)
            ],
            "provenance": provenance(db, problem.id),
            "quality": quality(db, problem.id),
            "versions": versions,
            "merges": merges,
            "audits": [
                {
                    "id": audit.id,
                    "action": audit.action,
                    "actor_id": audit.actor_id,
                    "timestamp": audit.timestamp,
                }
                for audit in audits
            ],
        }
    )
    return data
