from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, or_, select

from src.database import get_session
from src.models import Atom

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[Atom])
def search_atoms(
    q: str = Query(min_length=1),
    session: Session = Depends(get_session),
) -> list[Atom]:
    """Search atoms by concept or explanation using case-insensitive matching."""
    statement = select(Atom).where(
        or_(
            Atom.concept.ilike(f"%{q}%"),
            Atom.explanation.ilike(f"%{q}%"),
        )
    ).limit(20)
    return list(session.exec(statement).all())
