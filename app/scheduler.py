from datetime import datetime, timezone
from typing import Any, Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import settings
from app.database import SessionLocal
from app.collectors.rss_collector import RSSCollector
from app.clustering.event_clusterer import EventClusterer

_scheduler: Optional[BackgroundScheduler] = None
_last_run_at: Optional[datetime] = None
_last_run_summary: Dict[str, Any] = {}


def run_collection_and_clustering_cycle() -> Dict[str, Any]:
    """Executa um ciclo completo de coleta RSS e agrupamento de eventos."""
    global _last_run_at, _last_run_summary
    with SessionLocal() as db:
        collector = RSSCollector(db=db)
        new_articles = collector.collect_all_sources()
        clusterer = EventClusterer(db=db)
        events = clusterer.cluster_articles()
        _last_run_at = datetime.now(timezone.utc)
        _last_run_summary = {
            "last_run_at": _last_run_at.isoformat(),
            "new_articles_count": len(new_articles),
            "events_count": len(events),
        }
        return _last_run_summary


def start_scheduler() -> BackgroundScheduler:
    """Inicia o APScheduler em background com intervalo COLLECT_INTERVAL_MINUTES."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_collection_and_clustering_cycle,
        trigger="interval",
        minutes=settings.COLLECT_INTERVAL_MINUTES,
        id="contraponto_rss_collect_cluster",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    """Encerra o APScheduler caso esteja em execução."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def get_scheduler_status() -> Dict[str, Any]:
    """Retorna o status atual do agendador periódico para o endpoint /health."""
    running = bool(_scheduler is not None and _scheduler.running)
    return {
        "running": running,
        "interval_minutes": settings.COLLECT_INTERVAL_MINUTES,
        "last_run_at": _last_run_at.isoformat() if _last_run_at else None,
        "last_summary": _last_run_summary,
    }
