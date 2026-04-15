from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from src.database import get_session
from src.models import Card
from src.sm2 import sm2

router = APIRouter(prefix="/cards", tags=["cards"])


class ReviewPayload(SQLModel):
    quality: int


@router.get("", response_model=list[Card])
def list_cards(session: Session = Depends(get_session)) -> list[Card]:
    """List all cards."""
    return list(session.exec(select(Card)).all())


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
