from typing import Callable
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app.models import AnalysisJob, Event, utcnow
from app.schemas import AnalyzeTriggerResponse
from app.clustering.event_clusterer import select_divergent_articles
from app.analysis.analysis_jobs import execute_analysis_job
from app.analysis.llm_client import LlamaCppClient
from app.api.routes_events import ensure_demo_seed

router = APIRouter(prefix="/events", tags=["analysis"])


def get_llm_client() -> LlamaCppClient:
    """Provedor injetável do cliente llama.cpp para rotas de análise."""
    return LlamaCppClient()


def get_job_session_factory() -> Callable[[], Session]:
    """Provedor injetável da fábrica de sessão para o job em background."""
    return SessionLocal


@router.post(
    "/{event_id}/analyze",
    response_model=AnalyzeTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_event_analysis(
    event_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    llm_client: LlamaCppClient = Depends(get_llm_client),
    session_factory: Callable[[], Session] = Depends(get_job_session_factory),
) -> AnalyzeTriggerResponse:
    """
    Inicia assincronamente o job de análise do evento via BackgroundTasks
    e responde imediatamente HTTP 202 com {"analysis_id": "...", "status": "queued"}.
    Nunca executa a análise de forma síncrona dentro da requisição.
    """
    ensure_demo_seed(db)
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evento '{event_id}' não encontrado.",
        )

    selected_articles = select_divergent_articles(db, event_id=event.id, max_articles=4)
    if not selected_articles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"O evento '{event_id}' não possui matérias vinculadas para análise.",
        )

    selected_ids = [a.id for a in selected_articles]

    # Se houver um job anterior interrompido/falho, preserva completed_article_ids para retomada
    prior_job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.event_id == event.id, AnalysisJob.status.in_(["failed", "running", "queued"]))
        .order_by(AnalysisJob.criado_em.desc())
        .first()
    )

    if prior_job is not None:
        kept_completed = [
            aid for aid in (prior_job.completed_article_ids or [])
            if aid in selected_ids
        ]
        prior_job.selected_article_ids = selected_ids
        prior_job.completed_article_ids = kept_completed
        prior_job.articles_total = len(selected_ids)
        prior_job.articles_done = len(kept_completed)
        prior_job.status = "queued"
        prior_job.stage = f"bias_{len(kept_completed) + 1}_de_{len(selected_ids)}"
        prior_job.error = None
        prior_job.atualizado_em = utcnow()
        db.add(prior_job)
        db.commit()
        db.refresh(prior_job)
        job = prior_job
    else:
        job = AnalysisJob(
            event_id=event.id,
            status="queued",
            stage=f"bias_1_de_{len(selected_ids)}",
            articles_done=0,
            articles_total=len(selected_ids),
            selected_article_ids=selected_ids,
            completed_article_ids=[],
            error=None,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    background_tasks.add_task(
        execute_analysis_job,
        job_id=job.id,
        db=None,
        llm_client=llm_client,
        session_factory=session_factory,
    )

    return AnalyzeTriggerResponse(
        analysis_id=job.id,
        status="queued",
    )
