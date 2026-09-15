import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate
from app.services import catalog

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(data: SourceCreate, db: Session = Depends(get_db)) -> SourceRead:
    return catalog.create_source(db, data)


@router.get("", response_model=list[SourceRead])
def list_sources(db: Session = Depends(get_db)) -> list[SourceRead]:
    return catalog.list_sources(db)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: uuid.UUID, db: Session = Depends(get_db)) -> SourceRead:
    return catalog.get_source(db, source_id)


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    source_id: uuid.UUID, data: SourceUpdate, db: Session = Depends(get_db)
) -> SourceRead:
    return catalog.update_source(db, source_id, data)
