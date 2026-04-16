from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

from src.config import load_config
from src import models  # noqa: F401 - ensures SQLModel metadata is registered


def _load_database_url() -> str:
    """Load the database URL from configs/config.yaml."""
    config = load_config()
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
