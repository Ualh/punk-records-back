from pathlib import Path
from uuid import uuid4

import requests
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Field, Session, SQLModel, func, select

from src.config import load_config
from src.database import get_session
from src.ingestion.pipeline import ingest_pdf
from src.models import Atom, Card, Source, SourceCreate

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceSummary(SQLModel):
    """Source payload enriched with aggregate study counters."""

    id: int
    title: str
    type: str
    file_path: str | None = None
    created_at: str
    atom_count: int
    card_count: int
    tags: list[str] = Field(default_factory=list)


def _serialize_source(source: Source) -> dict:
    """Return a stable JSON-ready source payload."""
    return {
        "id": source.id,
        "title": source.title,
        "type": source.type,
        "file_path": source.file_path,
        "created_at": source.created_at.isoformat(),
    }


@router.get("", response_model=list[SourceSummary])
def list_sources(session: Session = Depends(get_session)) -> list[SourceSummary]:
    """List all sources with atom and card counters for UI summaries."""
    sources = list(session.exec(select(Source)).all())
    summaries: list[SourceSummary] = []

    for source in sources:
        if source.id is None:
            continue

        atom_count = session.exec(
            select(func.count(Atom.id)).where(Atom.source_id == source.id)
        ).one()
        card_count = session.exec(
            select(func.count(Card.id)).where(
                Card.atom_id.in_(select(Atom.id).where(Atom.source_id == source.id))
            )
        ).one()
        summaries.append(
            SourceSummary(
                id=source.id,
                title=source.title,
                type=source.type,
                file_path=source.file_path,
                created_at=source.created_at.isoformat(),
                atom_count=int(atom_count or 0),
                card_count=int(card_count or 0),
                tags=[],
            )
        )

    return summaries


@router.post("", response_model=Source)
def create_source(payload: SourceCreate, session: Session = Depends(get_session)) -> Source:
    """Create a source entry."""
    source = Source(
        title=payload.title,
        type=payload.type,
        file_path=payload.file_path,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@router.post("/upload")
async def upload_source(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict:
    """Upload a PDF source and trigger ingestion."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    config = load_config()
    upload_dir = Path(config["ingestion"]["upload_dir"])
    upload_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid4().hex}{suffix}"
    stored_path = upload_dir / stored_name
    stored_path.write_bytes(await file.read())

    source = Source(
        title=Path(file.filename).stem,
        type="pdf",
        file_path=str(stored_path),
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    try:
        summary = ingest_pdf(source_id=source.id, file_path=stored_path, session=session)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach Ollama during ingestion: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"source": _serialize_source(source), "ingestion": summary}
