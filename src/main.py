from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import create_db_and_tables
from src.routes.atoms import router as atoms_router
from src.routes.cards import router as cards_router
from src.routes.sources import router as sources_router

app = FastAPI(title="Punk_Records API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Initialize local database on API startup."""
    create_db_and_tables()


@app.get("/health")
def health() -> dict[str, str]:
    """Simple service liveness check."""
    return {"status": "ok"}


app.include_router(sources_router)
app.include_router(atoms_router)
app.include_router(cards_router)
