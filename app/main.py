from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db, init_db
from app.models import Source
from app.schemas import HealthResponse
from app.scheduler import get_scheduler_status, start_scheduler, stop_scheduler
from app.analysis.llm_client import LlamaCppClient
from app.api.routes_analysis import get_llm_client, router as analysis_router
from app.api.routes_articles import router as articles_router
from app.api.routes_decks import router as decks_router
from app.api.routes_dossier import router as dossier_router
from app.api.routes_events import router as events_router
from app.api.routes_sources import router as sources_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Inicializa estrutura do banco de dados e agendador periódico no ciclo de vida da aplicação."""
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title="Contraponto API",
    description=(
        "Toda notícia tem enquadramento. Análise sob ótica marxista-leninista. "
        "Agregador crítico de notícias e gerador de Dossiês de Contradição."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check(
    db: Session = Depends(get_db),
    llm_client: LlamaCppClient = Depends(get_llm_client),
) -> HealthResponse:
    """
    Retorna o status do banco, llama-server (GET /health e modelo em GET /props),
    Qdrant ('disabled' se USE_QDRANT=false), agendador e última coleta por fonte.
    """
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    llama_info = llm_client.check_health()

    if not settings.USE_QDRANT:
        qdrant_info: Dict[str, Any] = {
            "status": "disabled",
            "enabled": False,
            "url": settings.QDRANT_URL,
        }
    else:
        try:
            from qdrant_client import QdrantClient
            qclient = QdrantClient(url=settings.QDRANT_URL, timeout=3)
            qclient.get_collections()
            qdrant_info = {
                "status": "ok",
                "enabled": True,
                "url": settings.QDRANT_URL,
            }
        except Exception as exc:
            qdrant_info = {
                "status": "unreachable",
                "enabled": True,
                "url": settings.QDRANT_URL,
                "error": str(exc),
            }

    sources_last_collection: Dict[str, Optional[str]] = {}
    try:
        for src in db.query(Source).all():
            sources_last_collection[src.id] = (
                src.ultima_coleta.isoformat() if src.ultima_coleta else None
            )
    except Exception:
        pass

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        llama_server=llama_info,
        qdrant=qdrant_info,
        scheduler=get_scheduler_status(),
        sources_last_collection=sources_last_collection,
    )


app.include_router(articles_router)
app.include_router(sources_router)
app.include_router(events_router)
app.include_router(analysis_router)
app.include_router(dossier_router)
app.include_router(decks_router)
