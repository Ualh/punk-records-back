from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import src.database as database
from src.main import app
from src.models import Atom, Card, Source


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(database, "engine", engine)
    SQLModel.metadata.create_all(engine)

    with TestClient(app) as test_client:
        yield test_client


def test_create_atom_rejects_client_supplied_id(client: TestClient) -> None:
    response = client.post(
        "/atoms",
        json={
            "id": 99,
            "source_id": 1,
            "concept": "Signal",
            "explanation": "Meaning carried through a channel.",
            "tags": ["comms"],
        },
    )

    assert response.status_code == 422


def test_create_atom_requires_existing_source(client: TestClient) -> None:
    response = client.post(
        "/atoms",
        json={
            "source_id": 999,
            "concept": "Signal",
            "explanation": "Meaning carried through a channel.",
            "tags": ["comms"],
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Source 999 not found"}


def test_list_atoms_can_filter_by_source_id(client: TestClient) -> None:
    with Session(database.engine) as session:
        source_a = Source(title="A", type="note")
        source_b = Source(title="B", type="note")
        session.add(source_a)
        session.add(source_b)
        session.commit()
        session.refresh(source_a)
        session.refresh(source_b)

        session.add(
            Atom(
                source_id=source_a.id,
                concept="concept-a",
                explanation="exp-a",
                tags='["a"]',
            )
        )
        session.add(
            Atom(
                source_id=source_b.id,
                concept="concept-b",
                explanation="exp-b",
                tags='["b"]',
            )
        )
        session.commit()

        source_a_id = source_a.id

    response = client.get(f"/atoms?source_id={source_a_id}")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["source_id"] == source_a_id
    assert payload[0]["concept"] == "concept-a"


def test_list_sources_includes_atom_and_card_counts(client: TestClient) -> None:
    with Session(database.engine) as session:
        source_a = Source(title="A", type="note")
        source_b = Source(title="B", type="note")
        session.add(source_a)
        session.add(source_b)
        session.commit()
        session.refresh(source_a)
        session.refresh(source_b)

        atom_a1 = Atom(source_id=source_a.id, concept="a1", explanation="e1")
        atom_a2 = Atom(source_id=source_a.id, concept="a2", explanation="e2")
        atom_b1 = Atom(source_id=source_b.id, concept="b1", explanation="e3")
        session.add(atom_a1)
        session.add(atom_a2)
        session.add(atom_b1)
        session.commit()
        session.refresh(atom_a1)
        session.refresh(atom_a2)

        session.add(Card(atom_id=atom_a1.id, front="q1", back="a1"))
        session.add(Card(atom_id=atom_a2.id, front="q2", back="a2"))
        session.commit()

    response = client.get("/sources")

    assert response.status_code == 200
    payload = response.json()
    by_title = {entry["title"]: entry for entry in payload}

    assert by_title["A"]["atom_count"] == 2
    assert by_title["A"]["card_count"] == 2
    assert by_title["A"]["tags"] == []
    assert by_title["B"]["atom_count"] == 1
    assert by_title["B"]["card_count"] == 0


def test_list_cards_can_filter_by_source_and_returns_metadata(client: TestClient) -> None:
    with Session(database.engine) as session:
        source_a = Source(title="A", type="note")
        source_b = Source(title="B", type="note")
        session.add(source_a)
        session.add(source_b)
        session.commit()
        session.refresh(source_a)
        session.refresh(source_b)

        atom_a = Atom(
            source_id=source_a.id,
            concept="Concept A",
            explanation="exp-a",
            tags='["a-tag"]',
        )
        atom_b = Atom(
            source_id=source_b.id,
            concept="Concept B",
            explanation="exp-b",
            tags='["b-tag"]',
        )
        session.add(atom_a)
        session.add(atom_b)
        session.commit()
        session.refresh(atom_a)
        session.refresh(atom_b)

        card_a = Card(atom_id=atom_a.id, front="qa", back="aa")
        card_b = Card(atom_id=atom_b.id, front="qb", back="ab")
        session.add(card_a)
        session.add(card_b)
        session.commit()

        source_a_id = source_a.id

    response = client.get("/cards", params={"source_id": source_a_id})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["front"] == "qa"
    assert payload[0]["source_id"] == source_a_id
    assert payload[0]["source_title"] == "A"
    assert payload[0]["atom_concept"] == "Concept A"
    assert payload[0]["tags"] == ["a-tag"]


def test_search_atoms_matches_concept_and_explanation(client: TestClient) -> None:
    with Session(database.engine) as session:
        source = Source(title="Search Source", type="note")
        session.add(source)
        session.commit()
        session.refresh(source)

        session.add(
            Atom(
                source_id=source.id,
                concept="Memory consolidation",
                explanation="Sleep supports memory consolidation.",
            )
        )
        session.add(
            Atom(
                source_id=source.id,
                concept="Spacing effect",
                explanation="Active recall improves retention over time.",
            )
        )
        session.commit()

    by_explanation = client.get("/search", params={"q": "sleep"})
    assert by_explanation.status_code == 200
    explanation_payload = by_explanation.json()
    assert len(explanation_payload) == 1
    assert explanation_payload[0]["concept"] == "Memory consolidation"

    by_concept = client.get("/search", params={"q": "spacing"})
    assert by_concept.status_code == 200
    concept_payload = by_concept.json()
    assert len(concept_payload) == 1
    assert concept_payload[0]["concept"] == "Spacing effect"


def test_upload_source_creates_pdf_source_and_returns_ingestion_summary(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload_dir = tmp_path / "uploads"

    monkeypatch.setattr(
        "src.routes.sources.load_config",
        lambda: {"ingestion": {"upload_dir": str(upload_dir)}},
    )
    monkeypatch.setattr(
        "src.routes.sources.ingest_pdf",
        lambda source_id, file_path, session: {"chunks": 1, "atoms": 2, "cards": 2},
    )

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Communication improves with clarity.")
    pdf_bytes = document.write()
    document.close()

    response = client.post(
        "/sources/upload",
        files={"file": ("communication.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["id"] == 1
    assert payload["source"]["title"] == "communication"
    assert payload["source"]["type"] == "pdf"
    assert payload["ingestion"] == {"chunks": 1, "atoms": 2, "cards": 2}

    with Session(database.engine) as session:
        sources = list(session.exec(select(Source)).all())

    assert len(sources) == 1
    assert Path(sources[0].file_path).exists()
