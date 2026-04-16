from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

import src.database as database
from src.main import app
from src.models import Source


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
