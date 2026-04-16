import json
import logging
from pathlib import Path

import fitz
import requests
from sqlmodel import Session

from src.config import load_config
from src.models import Atom, AtomCreate, Card, Source

logger = logging.getLogger(__name__)


def extract_pdf_text(file_path: Path) -> str:
    """Extract plain text from a PDF file."""
    with fitz.open(file_path) as document:
        pages = [page.get_text("text").strip() for page in document]
    return "\n\n".join(page for page in pages if page)


def chunk_text(text: str, chunk_size: int) -> list[str]:
    """Split extracted text into fixed-size chunks."""
    normalized_text = " ".join(text.split())
    if not normalized_text:
        return []

    return [
        normalized_text[index : index + chunk_size]
        for index in range(0, len(normalized_text), chunk_size)
    ]


def _build_extraction_prompt(chunk: str, max_atoms: int) -> str:
    """Build the extraction prompt for a single text chunk."""
    return f"""
Extract up to {max_atoms} knowledge atoms from the text below.
Return only a raw JSON array.
Each array item must have: concept, explanation, tags, atom_type.
The tags field must be an array of short strings.
The atom_type must be one of: knowledge, thought, note, summary.

Text:
{chunk}
""".strip()


def _strip_json_fences(raw_response: str) -> str:
    """Remove optional markdown fences from a model response."""
    cleaned = raw_response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    return cleaned.strip()


def extract_atoms_from_chunk(chunk: str) -> list[AtomCreate]:
    """Call Ollama and parse atom payloads for one chunk."""
    config = load_config()
    ollama_config = config["ollama"]
    ingestion_config = config["ingestion"]
    prompt = _build_extraction_prompt(chunk, int(ingestion_config["max_atoms_per_chunk"]))

    response = requests.post(
        f'{ollama_config["base_url"].rstrip("/")}/api/generate',
        json={
            "model": ollama_config["models"]["extraction"],
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=int(ollama_config["timeout_seconds"]),
    )
    response.raise_for_status()

    raw_response = str(response.json()["response"])
    cleaned_response = _strip_json_fences(raw_response)

    try:
        parsed = json.loads(cleaned_response)
    except json.JSONDecodeError:
        logger.warning(
            "Skipping chunk after JSON parse failure. chunk_preview=%r raw_response_preview=%r",
            chunk[:200],
            raw_response[:200],
        )
        return []

    if isinstance(parsed, dict):
        parsed = [parsed]
    elif not isinstance(parsed, list):
        logger.warning(
            "Skipping chunk because model response was not valid atom JSON. raw_response_preview=%r",
            raw_response[:200],
        )
        return []

    atoms: list[AtomCreate] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue

        try:
            atoms.append(
                AtomCreate(
                    source_id=0,
                    concept=str(item["concept"]).strip(),
                    explanation=str(item["explanation"]).strip(),
                    tags=[str(tag).strip() for tag in item.get("tags", []) if str(tag).strip()],
                    atom_type=str(item.get("atom_type", "knowledge")).strip() or "knowledge",
                )
            )
        except (KeyError, TypeError, ValueError):
            logger.warning("Skipping malformed atom payload. payload_preview=%r", item)

    return atoms


def ingest_pdf(source_id: int, file_path: Path, session: Session) -> dict[str, int]:
    """Ingest a PDF into atoms and cards for an existing source."""
    source = session.get(Source, source_id)
    if not source:
        raise ValueError(f"Source {source_id} not found")

    extracted_text = extract_pdf_text(file_path)
    if not extracted_text.strip():
        return {"chunks": 0, "atoms": 0, "cards": 0}

    chunk_size = int(load_config()["ingestion"]["chunk_size"])
    chunks = chunk_text(extracted_text, chunk_size)

    created_atoms = 0
    created_cards = 0

    for chunk in chunks:
        atom_payloads = extract_atoms_from_chunk(chunk)
        for payload in atom_payloads:
            atom = Atom(
                source_id=source_id,
                concept=payload.concept,
                explanation=payload.explanation,
                tags=json.dumps(payload.tags),
                atom_type=payload.atom_type,
            )
            session.add(atom)
            session.flush()

            card = Card(
                atom_id=atom.id,
                front=payload.concept,
                back=payload.explanation,
            )
            session.add(card)
            created_atoms += 1
            created_cards += 1

    session.commit()
    return {"chunks": len(chunks), "atoms": created_atoms, "cards": created_cards}
