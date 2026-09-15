import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models.document import Document
from app.models.problem import Problem
from app.models.source import Source
from app.schemas.document import DocumentCreate
from app.schemas.problem import ProblemCreate, ProblemUpdate
from app.schemas.source import SourceCreate, SourceUpdate
from app.services.pipeline import digest


def create_source(db: Session, data: SourceCreate) -> Source:
    source = Source(
        **data.model_dump(exclude={"url", "metadata"}),
        url=str(data.url) if data.url else None,
        metadata_=data.metadata,
    )
    if data.content:
        source.content_hash = digest(data.content)
    db.add(source)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "DUPLICATE_SOURCE", "A source with matching content already exists."
        ) from exc
    db.refresh(source)
    return source


def get_source(db: Session, source_id: uuid.UUID) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise NotFoundError("SOURCE_NOT_FOUND", "Source does not exist.")
    return source


def list_sources(db: Session) -> list[Source]:
    return list(db.scalars(select(Source).order_by(Source.created_at.desc())))


def update_source(db: Session, source_id: uuid.UUID, data: SourceUpdate) -> Source:
    source = get_source(db, source_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    db.refresh(source)
    return source


def create_document(db: Session, data: DocumentCreate) -> Document:
    get_source(db, data.source_id)
    document = Document(**data.model_dump())
    db.add(document)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "DOCUMENT_CONFLICT", "A matching document already exists for this source."
        ) from exc
    db.refresh(document)
    return document


def get_document(db: Session, document_id: uuid.UUID) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Document does not exist.")
    return document


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


def create_problem(db: Session, data: ProblemCreate) -> Problem:
    problem = Problem(**data.model_dump())
    db.add(problem)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("PROBLEM_CONFLICT", "Problem ID or slug already exists.") from exc
    db.refresh(problem)
    return problem


def get_problem(db: Session, problem_id: uuid.UUID) -> Problem:
    problem = db.get(Problem, problem_id)
    if problem is None or problem.deleted:
        raise NotFoundError("PROBLEM_NOT_FOUND", "Problem does not exist.")
    return problem


def list_problems(db: Session) -> list[Problem]:
    return list(
        db.scalars(
            select(Problem).where(Problem.deleted.is_(False)).order_by(Problem.created_at.desc())
        )
    )


def update_problem(db: Session, problem_id: uuid.UUID, data: ProblemUpdate) -> Problem:
    problem = get_problem(db, problem_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(problem, field, value)
    db.commit()
    db.refresh(problem)
    return problem


def delete_problem(db: Session, problem_id: uuid.UUID) -> None:
    problem = get_problem(db, problem_id)
    problem.deleted = True
    db.commit()
