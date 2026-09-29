import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import CanonicalProblemStatus
from app.schemas.canonical import (
    CanonicalizationCreate,
    CanonicalLifecycleChange,
    CanonicalMergeCreate,
    CanonicalProblemCreate,
    CanonicalProblemMergeRead,
    CanonicalProblemRead,
    CanonicalProblemUpdate,
    CanonicalProblemVersionRead,
    CanonicalResolutionCreate,
    CanonicalVersionCreate,
    ProblemCanonicalizationRead,
)
from app.services import canonical as canonical_service
from app.services import resolution as resolution_service

router = APIRouter(prefix="/canonical-problems", tags=["canonical problems"])


@router.post("", response_model=CanonicalProblemRead, status_code=status.HTTP_201_CREATED)
def create_canonical_problem(
    data: CanonicalProblemCreate, db: Session = Depends(get_db)
) -> CanonicalProblemRead:
    return canonical_service.create_canonical_problem(db, data)


@router.get("/{canonical_problem_id}", response_model=CanonicalProblemRead)
def get_canonical_problem(
    canonical_problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> CanonicalProblemRead:
    return canonical_service.get_canonical_problem(db, canonical_problem_id)


@router.patch("/{canonical_problem_id}", response_model=CanonicalProblemRead)
def update_canonical_problem(
    canonical_problem_id: uuid.UUID,
    data: CanonicalProblemUpdate,
    db: Session = Depends(get_db),
) -> CanonicalProblemRead:
    return canonical_service.update_canonical_problem(db, canonical_problem_id, data)


@router.post("/{canonical_problem_id}/activate", response_model=CanonicalProblemRead)
def activate_canonical_problem(
    canonical_problem_id: uuid.UUID,
    data: CanonicalLifecycleChange,
    db: Session = Depends(get_db),
) -> CanonicalProblemRead:
    return canonical_service.transition_canonical_problem(
        db, canonical_problem_id, CanonicalProblemStatus.ACTIVE, data
    )


@router.post("/{canonical_problem_id}/archive", response_model=CanonicalProblemRead)
def archive_canonical_problem(
    canonical_problem_id: uuid.UUID,
    data: CanonicalLifecycleChange,
    db: Session = Depends(get_db),
) -> CanonicalProblemRead:
    return canonical_service.transition_canonical_problem(
        db, canonical_problem_id, CanonicalProblemStatus.ARCHIVED, data
    )


@router.post("/{canonical_problem_id}/restore", response_model=CanonicalProblemRead)
def restore_canonical_problem(
    canonical_problem_id: uuid.UUID,
    data: CanonicalLifecycleChange,
    db: Session = Depends(get_db),
) -> CanonicalProblemRead:
    return canonical_service.transition_canonical_problem(
        db, canonical_problem_id, CanonicalProblemStatus.ACTIVE, data
    )


@router.post("/{canonical_problem_id}/retire", response_model=CanonicalProblemRead)
def retire_canonical_problem(
    canonical_problem_id: uuid.UUID,
    data: CanonicalLifecycleChange,
    db: Session = Depends(get_db),
) -> CanonicalProblemRead:
    return canonical_service.transition_canonical_problem(
        db, canonical_problem_id, CanonicalProblemStatus.RETIRED, data
    )


@router.post(
    "/{canonical_problem_id}/versions",
    response_model=CanonicalProblemVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_canonical_version(
    canonical_problem_id: uuid.UUID,
    data: CanonicalVersionCreate,
    db: Session = Depends(get_db),
) -> CanonicalProblemVersionRead:
    return canonical_service.create_canonical_version(db, canonical_problem_id, data)


@router.get("/{canonical_problem_id}/versions", response_model=list[CanonicalProblemVersionRead])
def canonical_version_history(
    canonical_problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[CanonicalProblemVersionRead]:
    return canonical_service.canonical_version_history(db, canonical_problem_id)


@router.get("/{canonical_problem_id}/versions/latest", response_model=CanonicalProblemVersionRead)
def latest_canonical_version(
    canonical_problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> CanonicalProblemVersionRead:
    return canonical_service.latest_canonical_version(db, canonical_problem_id)


@router.get(
    "/{canonical_problem_id}/versions/{version_number}",
    response_model=CanonicalProblemVersionRead,
)
def get_canonical_version(
    canonical_problem_id: uuid.UUID,
    version_number: int,
    db: Session = Depends(get_db),
) -> CanonicalProblemVersionRead:
    return canonical_service.get_canonical_version(db, canonical_problem_id, version_number)


@router.post(
    "/{canonical_problem_id}/canonicalizations",
    response_model=ProblemCanonicalizationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_canonicalization(
    canonical_problem_id: uuid.UUID,
    data: CanonicalizationCreate,
    db: Session = Depends(get_db),
) -> ProblemCanonicalizationRead:
    return canonical_service.create_canonicalization(db, canonical_problem_id, data)


@router.get(
    "/{canonical_problem_id}/canonicalizations", response_model=list[ProblemCanonicalizationRead]
)
def canonicalization_history(
    canonical_problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ProblemCanonicalizationRead]:
    return canonical_service.canonicalization_history(db, canonical_problem_id)


@router.post(
    "/{canonical_problem_id}/merge",
    response_model=CanonicalProblemMergeRead,
    status_code=status.HTTP_201_CREATED,
)
def execute_merge(
    canonical_problem_id: uuid.UUID,
    data: CanonicalMergeCreate,
    db: Session = Depends(get_db),
) -> CanonicalProblemMergeRead:
    return canonical_service.execute_merge(db, canonical_problem_id, data)


candidate_router = APIRouter(prefix="/problems", tags=["canonical problems"])


@candidate_router.get("/{problem_id}/canonicalization", response_model=ProblemCanonicalizationRead)
def current_canonical_mapping(
    problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> ProblemCanonicalizationRead:
    return canonical_service.current_canonical_mapping(db, problem_id)


@candidate_router.post(
    "/{problem_id}/canonicalization",
    response_model=ProblemCanonicalizationRead,
    status_code=status.HTTP_201_CREATED,
)
def resolve_canonical_identity(
    problem_id: uuid.UUID,
    data: CanonicalResolutionCreate,
    db: Session = Depends(get_db),
) -> ProblemCanonicalizationRead:
    return resolution_service.resolve_candidate(db, problem_id, data)


@candidate_router.get(
    "/{problem_id}/canonicalization/history", response_model=list[ProblemCanonicalizationRead]
)
def resolution_history(
    problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ProblemCanonicalizationRead]:
    return resolution_service.resolution_history(db, problem_id)


@candidate_router.get(
    "/{problem_id}/canonicalization/current", response_model=ProblemCanonicalizationRead
)
def current_resolution_mapping(
    problem_id: uuid.UUID, db: Session = Depends(get_db)
) -> ProblemCanonicalizationRead:
    return canonical_service.current_canonical_mapping(db, problem_id)
