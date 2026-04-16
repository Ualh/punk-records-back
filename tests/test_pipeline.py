from pathlib import Path

import fitz
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from src.ingestion import pipeline
from src.models import Atom, Card, Source


class FakeResponse:
    """Small fake HTTP response for Ollama tests."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        """Match requests.Response.raise_for_status."""

    def json(self) -> dict:
        """Return the mocked JSON body."""
        return self.payload


def test_extract_atoms_from_chunk_strips_code_fences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "load_config",
        lambda: {
            "ollama": {
                "base_url": "http://127.0.0.1:11434",
                "timeout_seconds": 30,
                "models": {"extraction": "llama3.1:8b"},
            },
            "ingestion": {"max_atoms_per_chunk": 5},
        },
    )
    monkeypatch.setattr(
        pipeline.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {
                "response": """```json
[
  {
    "concept": "Clarity",
    "explanation": "Clear language reduces ambiguity.",
    "tags": ["communication"],
    "atom_type": "knowledge"
  }
]
```"""
            }
        ),
    )

    atoms = pipeline.extract_atoms_from_chunk("Clear language matters.")

    assert len(atoms) == 1
    assert atoms[0].concept == "Clarity"
    assert atoms[0].tags == ["communication"]


def test_extract_atoms_from_chunk_accepts_single_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "load_config",
        lambda: {
            "ollama": {
                "base_url": "http://127.0.0.1:11434",
                "timeout_seconds": 30,
                "models": {"extraction": "llama3.1:8b"},
            },
            "ingestion": {"max_atoms_per_chunk": 5},
        },
    )
    monkeypatch.setattr(
        pipeline.requests,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {
                "response": """
{
  "concept": "Active listening",
  "explanation": "Listening carefully improves understanding.",
  "tags": ["communication"],
  "atom_type": "knowledge"
}
"""
            }
        ),
    )

    atoms = pipeline.extract_atoms_from_chunk("Listening carefully matters.")

    assert len(atoms) == 1
    assert atoms[0].concept == "Active listening"


def test_ingest_pdf_creates_atoms_and_cards(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'pipeline.db'}")
    SQLModel.metadata.create_all(engine)

    monkeypatch.setattr(
        pipeline,
        "load_config",
        lambda: {"ingestion": {"chunk_size": 1500}},
    )
    monkeypatch.setattr(
        pipeline,
        "extract_atoms_from_chunk",
        lambda chunk: [
            pipeline.AtomCreate(
                source_id=0,
                concept="Clarity",
                explanation="Clear language reduces ambiguity.",
                tags=["communication"],
                atom_type="knowledge",
            )
        ],
    )

    pdf_path = tmp_path / "fixture.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Clarity improves understanding.")
    document.save(pdf_path)
    document.close()

    with Session(engine) as session:
        source = Source(title="Fixture", type="pdf", file_path=str(pdf_path))
        session.add(source)
        session.commit()
        session.refresh(source)

        summary = pipeline.ingest_pdf(source.id, pdf_path, session)

        atoms = list(session.exec(select(Atom)).all())
        cards = list(session.exec(select(Card)).all())

    assert summary == {"chunks": 1, "atoms": 1, "cards": 1}
    assert len(atoms) == 1
    assert atoms[0].tags == '["communication"]'
    assert len(cards) == 1
    assert cards[0].front == "Clarity"
