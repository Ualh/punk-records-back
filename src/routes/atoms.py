import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.database import get_session
from src.models import Atom, AtomCreate, Source

router = APIRouter(prefix="/atoms", tags=["atoms"])


@router.get("", response_model=list[Atom])
def list_atoms(session: Session = Depends(get_session)) -> list[Atom]:
    """List all atoms in the vault."""
    return list(session.exec(select(Atom)).all())


@router.post("", response_model=Atom)
def create_atom(payload: AtomCreate, session: Session = Depends(get_session)) -> Atom:
    """Create one atom entry for an existing source."""
    source = session.get(Source, payload.source_id)
    if not source:
        raise HTTPException(
            status_code=404,
            detail=f"Source {payload.source_id} not found",
        )

    atom = Atom(
        source_id=payload.source_id,
        concept=payload.concept,
        explanation=payload.explanation,
        tags=json.dumps(payload.tags),
        atom_type=payload.atom_type,
    )
    session.add(atom)
    session.commit()
    session.refresh(atom)
    return atom
