from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from src.database import get_session
from src.models import Source

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[Source])
def list_sources(session: Session = Depends(get_session)) -> list[Source]:
    """List all sources in the vault."""
    return list(session.exec(select(Source)).all())


@router.post("", response_model=Source)
def create_source(source: Source, session: Session = Depends(get_session)) -> Source:
    """Create a source entry."""
    session.add(source)
    session.commit()
    session.refresh(source)
    return source
