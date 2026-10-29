from typing import Callable, List, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import AnalysisJob, Article, ArticleBiasAnalysis, Event, utcnow
from app.schemas import AnalysisStatusResponse, CoveragePairSchema
from app.clustering.event_clusterer import select_divergent_articles
from app.analysis.bias_analyzer import analyze_article_bias
from app.analysis.llm_client import LlamaCppClient
from app.analysis.marxist_analyzer import consolidate_event_marxist_analysis


def create_or_resume_analysis_job(
    db: Session,
    event_id: str,
    max_articles: int = 4,
) -> AnalysisJob:
    """
    Cria um novo job de análise ou retoma um job anterior interrompido/falho
    preservando os artigos já analisados (completed_article_ids).
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise ValueError(f"Evento não encontrado: {event_id}")

    selected_articles = select_divergent_articles(db, event_id=event_id, max_articles=max_articles)
    selected_ids = [a.id for a in selected_articles]

    existing_job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.event_id == event_id)
        .order_by(AnalysisJob.criado_em.desc())
        .first()
    )

    if existing_job is not None and existing_job.status in ("queued", "running", "failed"):
        kept_completed = [
            aid for aid in (existing_job.completed_article_ids or [])
            if aid in selected_ids
        ]
        existing_job.selected_article_ids = selected_ids
        existing_job.completed_article_ids = kept_completed
        existing_job.articles_total = len(selected_ids)
        existing_job.articles_done = len(kept_completed)
        existing_job.status = "queued"
        existing_job.stage = (
            f"bias_{len(kept_completed) + 1}_de_{len(selected_ids)}"
            if len(kept_completed) < len(selected_ids) and len(selected_ids) > 0
            else "consolidacao"
        )
        existing_job.error = None
        existing_job.atualizado_em = utcnow()
        db.add(existing_job)
        db.commit()
        db.refresh(existing_job)
        return existing_job

    job = AnalysisJob(
        event_id=event_id,
        status="queued",
        stage=f"bias_1_de_{len(selected_ids)}" if selected_ids else "consolidacao",
        articles_done=0,
        articles_total=len(selected_ids),
        selected_article_ids=selected_ids,
        completed_article_ids=[],
        error=None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def execute_analysis_job(
    job_id: str,
    db: Optional[Session] = None,
    llm_client: Optional[LlamaCppClient] = None,
    session_factory: Callable[[], Session] = SessionLocal,
) -> AnalysisJob:
    """
    Executa o pipeline completo de análise (Etapas 3.1, 3.2 e 3.3) de forma retomável.
    Persiste o progresso após cada matéria concluída.
    """
    own_session = db is None
    session = db or session_factory()
    client = llm_client or LlamaCppClient()

    try:
        job = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job is None:
            raise ValueError(f"AnalysisJob não encontrado: {job_id}")

        event = session.query(Event).filter(Event.id == job.event_id).first()
        if event is None:
            raise ValueError(f"Evento não encontrado para o job: {job.event_id}")

        if not job.selected_article_ids:
            selected_arts = select_divergent_articles(session, event.id, max_articles=4)
            job.selected_article_ids = [a.id for a in selected_arts]
            job.articles_total = len(job.selected_article_ids)

        total_articles = len(job.selected_article_ids)
        job.status = "running"
        job.error = None
        job.atualizado_em = utcnow()
        session.add(job)
        session.commit()

        articles_by_id = {
            a.id: a
            for a in session.query(Article)
            .filter(Article.id.in_(job.selected_article_ids))
            .all()
        }
        ordered_articles: List[Article] = [
            articles_by_id[aid]
            for aid in job.selected_article_ids
            if aid in articles_by_id
        ]

        coverage_pairs: List[CoveragePairSchema] = []
        completed_ids: List[str] = list(job.completed_article_ids or [])
        accumulated_ms = 0

        for idx, article in enumerate(ordered_articles, start=1):
            job.stage = f"bias_{idx}_de_{total_articles}"
            job.atualizado_em = utcnow()
            session.add(job)
            session.commit()

            existing_bias = (
                session.query(ArticleBiasAnalysis)
                .filter(
                    ArticleBiasAnalysis.article_id == article.id,
                    ArticleBiasAnalysis.event_id == event.id,
                )
                .first()
            )

            if article.id in completed_ids and existing_bias is not None:
                pair = CoveragePairSchema.model_validate(existing_bias.payload)
                coverage_pairs.append(pair)
                accumulated_ms += existing_bias.tempo_execucao_ms
                continue

            pair, meta, _ = analyze_article_bias(
                article=article,
                llm_client=client,
                db=session,
                max_attempts=3,
            )
            coverage_pairs.append(pair)
            accumulated_ms += meta.execution_time_ms

            if article.id not in completed_ids:
                completed_ids.append(article.id)
            job.completed_article_ids = list(completed_ids)
            job.articles_done = len(completed_ids)
            job.modelo_llm = meta.model_name
            job.num_ctx = meta.num_ctx
            job.atualizado_em = utcnow()
            session.add(job)
            session.commit()

        job.stage = "consolidacao"
        job.atualizado_em = utcnow()
        session.add(job)
        session.commit()

        _, consolidation_meta = consolidate_event_marxist_analysis(
            event=event,
            articles=ordered_articles,
            coverage_pairs=coverage_pairs,
            llm_client=client,
            db=session,
            prior_execution_ms=accumulated_ms,
        )

        job.status = "completed"
        job.stage = "consolidacao"
        job.articles_done = total_articles
        job.modelo_llm = consolidation_meta.model_name
        job.num_ctx = consolidation_meta.num_ctx
        job.error = None
        job.atualizado_em = utcnow()
        session.add(job)
        session.commit()
        session.refresh(job)
        return job

    except Exception as exc:
        job_err = session.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job_err is not None:
            job_err.status = "failed"
            job_err.error = str(exc)
            job_err.atualizado_em = utcnow()
            session.add(job_err)
            session.commit()
            session.refresh(job_err)
            return job_err
        raise
    finally:
        if own_session:
            session.close()


def get_event_analysis_status(db: Session, event_id: str) -> AnalysisStatusResponse:
    """Retorna o status atual do job de análise de um evento."""
    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.event_id == event_id)
        .order_by(AnalysisJob.criado_em.desc())
        .first()
    )
    if job is not None:
        status_val = job.status if job.status in ("queued", "running", "completed", "failed") else "queued"
        return AnalysisStatusResponse(
            status=status_val,  # type: ignore[arg-type]
            stage=job.stage,
            articles_done=job.articles_done,
            articles_total=job.articles_total,
            error=job.error,
        )

    event = db.query(Event).filter(Event.id == event_id).first()
    if event is not None and event.event_analysis is not None:
        pair_count = len(event.event_analysis.dossier_payload.get("coverage_pairs", []))
        return AnalysisStatusResponse(
            status="completed",
            stage="consolidacao",
            articles_done=pair_count,
            articles_total=pair_count,
            error=None,
        )

    total_arts = db.query(Article).filter(Article.event_id == event_id).count()
    return AnalysisStatusResponse(
        status="queued",
        stage="aguardando",
        articles_done=0,
        articles_total=min(4, total_arts),
        error=None,
    )
