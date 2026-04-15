from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from src.database import get_session
from src.models import Atom

router = APIRouter(prefix="/atoms", tags=["atoms"])


@router.get("", response_model=list[Atom])
def list_atoms(session: Session = Depends(get_session)) -> list[Atom]:
    """List all atoms in the vault."""
    return list(session.exec(select(Atom)).all())


@router.post("", response_model=Atom)
def create_atom(atom: Atom, session: Session = Depends(get_session)) -> Atom:
    """Create one atom entry."""
    session.add(atom)
    session.commit()
    session.refresh(atom)
    return atom
