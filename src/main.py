from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import create_db_and_tables
from src.routes.atoms import router as atoms_router
from src.routes.cards import router as cards_router
from src.routes.search import router as search_router
from src.routes.sources import router as sources_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize local state on app startup."""
    create_db_and_tables()
    yield


app = FastAPI(title="Punk_Records API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict[str, str]:
    """Simple service liveness check."""
    return {"status": "ok"}


app.include_router(sources_router)
app.include_router(atoms_router)
app.include_router(cards_router)
app.include_router(search_router)
