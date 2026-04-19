import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Field, Session, SQLModel, select

from src.database import get_session
from src.models import Atom, Card, Source
from src.sm2 import sm2

router = APIRouter(prefix="/cards", tags=["cards"])


class ReviewPayload(SQLModel):
    quality: int


class CardSummary(SQLModel):
    """Card payload enriched with atom and source metadata."""

    id: int
    atom_id: int
    source_id: int
    front: str
    back: str
    interval: int
    ease_factor: float
    repetitions: int
    next_review: datetime
    source_title: str
    atom_concept: str
    tags: list[str] = Field(default_factory=list)


def _parse_tags(raw_tags: str) -> list[str]:
    """Decode JSON-encoded atom tags safely for API responses."""
    try:
        parsed = json.loads(raw_tags)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    return [tag for tag in parsed if isinstance(tag, str)]


@router.get("", response_model=list[CardSummary])
def list_cards(
    source_id: Optional[int] = Query(default=None),
    session: Session = Depends(get_session),
) -> list[CardSummary]:
    """List cards, optionally filtered by source, with metadata for UI views."""
    statement = (
        select(Card, Atom, Source)
        .join(Atom, Card.atom_id == Atom.id)
        .join(Source, Atom.source_id == Source.id)
        .order_by(Card.next_review)
    )

    if source_id is not None:
        statement = statement.where(Source.id == source_id)

    rows = session.exec(statement).all()
    return [
        CardSummary(
            id=card.id,
            atom_id=card.atom_id,
            source_id=atom.source_id,
            front=card.front,
            back=card.back,
            interval=card.interval,
            ease_factor=card.ease_factor,
            repetitions=card.repetitions,
            next_review=card.next_review,
            source_title=source.title,
            atom_concept=atom.concept,
            tags=_parse_tags(atom.tags),
        )
        for card, atom, source in rows
    ]


@router.post("", response_model=Card)
def create_card(card: Card, session: Session = Depends(get_session)) -> Card:
    """Create one card."""
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


@router.get("/due", response_model=list[Card])
def due_cards(session: Session = Depends(get_session)) -> list[Card]:
    """List cards due for review right now."""
    statement = select(Card).where(Card.next_review <= datetime.now()).order_by(Card.next_review)
    return list(session.exec(statement).all())


@router.post("/{card_id}/review", response_model=Card)
def review_card(
    card_id: int,
    payload: ReviewPayload,
    session: Session = Depends(get_session),
) -> Card:
    """Review a card and update SM-2 fields."""
    card = session.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"Card {card_id} not found")

    interval, ease_factor, repetitions, next_review = sm2(
        quality=payload.quality,
        repetitions=card.repetitions,
        ease_factor=card.ease_factor,
        interval=card.interval,
    )
    card.interval = interval
    card.ease_factor = ease_factor
    card.repetitions = repetitions
    card.next_review = next_review

    session.add(card)
    session.commit()
    session.refresh(card)
    return card
