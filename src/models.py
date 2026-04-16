from datetime import datetime
from typing import Optional

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel


class SourceCreate(SQLModel):
    """Payload for creating a source without client-managed fields."""

    model_config = ConfigDict(extra="forbid")

    title: str
    type: str
    file_path: Optional[str] = None


class Source(SQLModel, table=True):
    """A document or input the user has added to the vault."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    type: str  # pdf | note | voice | handwritten
    file_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


class AtomCreate(SQLModel):
    """Payload for creating an atom without client-managed fields."""

    model_config = ConfigDict(extra="forbid")

    source_id: int
    concept: str
    explanation: str
    tags: list[str] = Field(default_factory=list)
    atom_type: str = "knowledge"


class Atom(SQLModel, table=True):
    """A single knowledge unit extracted from a source."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="source.id")
    concept: str
    explanation: str
    tags: str = "[]"
    atom_type: str = "knowledge"  # knowledge | thought | note | summary
    created_at: datetime = Field(default_factory=datetime.now)


class Card(SQLModel, table=True):
    """An SM-2 flashcard derived from an atom."""

    id: Optional[int] = Field(default=None, primary_key=True)
    atom_id: int = Field(foreign_key="atom.id")
    front: str
    back: str
    interval: int = 1
    ease_factor: float = 2.5
    repetitions: int = 0
    next_review: datetime = Field(default_factory=datetime.now)
