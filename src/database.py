from pathlib import Path
from typing import Generator

import yaml
from sqlmodel import Session, SQLModel, create_engine

from src import models  # noqa: F401 - ensures SQLModel metadata is registered


def _load_database_url() -> str:
    """Load the database URL from configs/config.yaml."""
    config_path = Path(__file__).resolve().parent.parent / "configs" / "config.yaml"
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    return str(config["database"]["url"])


DATABASE_URL = _load_database_url()
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables() -> None:
    """Create all SQLModel tables if they do not exist."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for FastAPI dependency injection."""
    with Session(engine) as session:
        yield session
