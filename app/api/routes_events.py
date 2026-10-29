from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import AnalysisJob, Article, Event, EventAnalysis, Source, utcnow
from app.schemas import (
    AnalysisStatusResponse,
    ArticleSummaryOut,
    DossierAuditMetadata,
    DossierSchema,
    EventDetailOut,
    EventSummaryOut,
    PaginatedEventsResponse,
)
from app.collectors.html_extractor import compute_content_hash
from app.analysis.analysis_jobs import get_event_analysis_status
from app.analysis.evidence_verifier import verify_dossier_payload_quotes
from app.analysis.marxist_analyzer import build_articles_audit_registry

router = APIRouter(prefix="/events", tags=["events"])

DEFAULT_DEMO_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "demo_event.yaml"


def _parse_iso_dt(val: object) -> datetime:
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str) and val:
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return utcnow()


def ensure_demo_seed(
    db: Session,
    fixture_path: Optional[Path] = None,
) -> Optional[Event]:
    """
    Popula o evento de demonstração 100% sintético a partir de tests/fixtures/demo_event.yaml
    caso o banco de eventos esteja vazio.
    Inviolável: todos os veículos e dados do seed são fictícios e marcados com is_demo=True.
    """
    if db.query(Event).count() > 0:
        return None

    path = fixture_path or DEFAULT_DEMO_FIXTURE_PATH
    if not path.exists():
        return None

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources_data = raw.get("sources", [])
    event_data = raw.get("event", {})
    articles_data = raw.get("articles", [])
    dossier_data = raw.get("dossier", {})

    if not event_data or not articles_data:
        return None

    for s_item in sources_data:
        existing_src = db.query(Source).filter(Source.id == s_item["id"]).first()
        if existing_src is None:
            db.add(
                Source(
                    id=s_item["id"],
                    nome=s_item["nome"],
                    url_rss=s_item["url_rss"],
                    categoria_editorial=s_item["categoria_editorial"],
                    pais=s_item.get("pais", "BR"),
                    idioma=s_item.get("idioma", "pt"),
                    posicao_editorial_declarada=s_item["posicao_editorial_declarada"],
                    descricao=s_item["descricao"],
                    ativo=True,
                    is_demo=True,
                )
            )
    db.commit()

    event_obj = Event(
        id=event_data["id"],
        titulo_provisorio=event_data["titulo_provisorio"],
        resumo=event_data["resumo"],
        periodo_inicio=_parse_iso_dt(event_data.get("periodo_inicio")),
        periodo_fim=_parse_iso_dt(event_data.get("periodo_fim")),
        score_coesao=float(event_data.get("score_coesao", 0.91)),
        tema=event_data.get("tema", "trabalho"),
        local=event_data.get("local"),
        lat=event_data.get("lat"),
        lon=event_data.get("lon"),
        is_demo=True,
    )
    db.add(event_obj)
    db.commit()
    db.refresh(event_obj)

    persisted_articles: List[Article] = []
    articles_text_by_id: Dict[str, str] = {}

    for a_item in articles_data:
        texto_limpo = str(a_item["texto_limpo"]).strip()
        titulo = str(a_item["titulo"]).strip()
        art_obj = Article(
            id=a_item["id"],
            source_id=a_item["source_id"],
            event_id=event_obj.id,
            titulo=titulo,
            url_canonica=a_item["url_canonica"],
            guid=a_item["guid"],
            veiculo=a_item["veiculo"],
            autor=a_item.get("autor"),
            data_publicacao=_parse_iso_dt(a_item.get("data_publicacao")),
            data_coleta=utcnow(),
            texto_limpo=texto_limpo,
            resumo=a_item["resumo"],
            idioma=a_item.get("idioma", "pt"),
            hash_conteudo=compute_content_hash(titulo, texto_limpo),
            metodo_coleta=a_item.get("metodo_coleta", "rss_full"),
            metadados={"is_demo": True, "synthetic_fixture": "tests/fixtures/demo_event.yaml"},
            is_demo=True,
        )
        db.add(art_obj)
        persisted_articles.append(art_obj)
        articles_text_by_id[art_obj.id] = f"{art_obj.titulo}\n{art_obj.resumo}\n{art_obj.texto_limpo}"

    db.commit()
    for a in persisted_articles:
        db.refresh(a)

    if dossier_data:
        verified_dossier_dict = verify_dossier_payload_quotes(
            dossier_dict=dict(dossier_data),
            articles_text_by_id=articles_text_by_id,
        )
        audit_meta = DossierAuditMetadata(
            analyzed_at=utcnow(),
            llm_model=f"{settings.LLAMA_CPP_MODEL} (Seed Sintético DEMO)",
            num_ctx=settings.LLAMA_CPP_NUM_CTX,
            execution_time_ms=0,
            is_demo=True,
            articles_registry=build_articles_audit_registry(db, persisted_articles),
        )
        verified_dossier_dict["audit_metadata"] = audit_meta.model_dump(mode="json")
        validated_dossier = DossierSchema.model_validate(verified_dossier_dict)

        ev_analysis = EventAnalysis(
            event_id=event_obj.id,
            dossier_payload=validated_dossier.model_dump(mode="json"),
            confidence=validated_dossier.confidence,
            modelo_llm=audit_meta.llm_model,
            num_ctx=settings.LLAMA_CPP_NUM_CTX,
            tempo_execucao_ms=0,
        )
        db.add(ev_analysis)

        demo_job = AnalysisJob(
            event_id=event_obj.id,
            status="completed",
            stage="consolidacao",
            articles_done=len(persisted_articles),
            articles_total=len(persisted_articles),
            selected_article_ids=[a.id for a in persisted_articles],
            completed_article_ids=[a.id for a in persisted_articles],
            error=None,
            modelo_llm=audit_meta.llm_model,
            num_ctx=settings.LLAMA_CPP_NUM_CTX,
        )
        db.add(demo_job)
        db.commit()

    db.refresh(event_obj)
    return event_obj


def _to_event_summary(event: Event) -> EventSummaryOut:
    has_dossier = event.event_analysis is not None
    confidence = event.event_analysis.confidence if event.event_analysis is not None else None
    return EventSummaryOut(
        id=event.id,
        titulo_provisorio=event.titulo_provisorio,
        resumo=event.resumo,
        periodo_inicio=event.periodo_inicio,
        periodo_fim=event.periodo_fim,
        score_coesao=event.score_coesao,
        tema=event.tema,
        local=event.local,
        lat=event.lat,
        lon=event.lon,
        is_demo=event.is_demo,
        articles_count=len(event.articles),
        has_dossier=has_dossier,
        confidence=confidence,
    )


def build_verified_dossier_for_event(db: Session, event: Event) -> Optional[DossierSchema]:
    """Reconstrói e revalida o DossierSchema de um evento garantindo verificação fuzzy e metadados."""
    if event.event_analysis is None:
        return None

    payload = dict(event.event_analysis.dossier_payload)
    articles_text_by_id = {
        a.id: f"{a.titulo}\n{a.resumo}\n{a.texto_limpo}"
        for a in event.articles
    }
    verified_payload = verify_dossier_payload_quotes(payload, articles_text_by_id)

    if not verified_payload.get("audit_metadata"):
        audit_meta = DossierAuditMetadata(
            analyzed_at=event.event_analysis.atualizado_em,
            llm_model=event.event_analysis.modelo_llm,
            num_ctx=event.event_analysis.num_ctx,
            execution_time_ms=event.event_analysis.tempo_execucao_ms,
            is_demo=event.is_demo,
            articles_registry=build_articles_audit_registry(db, event.articles),
        )
        verified_payload["audit_metadata"] = audit_meta.model_dump(mode="json")

    verified_payload["is_demo"] = event.is_demo
    verified_payload["title"] = verified_payload.get("title") or event.titulo_provisorio
    return DossierSchema.model_validate(verified_payload)


@router.get("", response_model=PaginatedEventsResponse)
def list_events(
    theme: Optional[str] = Query(default=None, description="Filtrar por tema do vocabulário controlado"),
    tema: Optional[str] = Query(default=None, description="Alias para filtro por tema"),
    limit: int = Query(default=20, ge=1, le=100, description="Itens por página (padrão 20, máx 100)"),
    offset: int = Query(default=0, ge=0, description="Deslocamento da paginação"),
    db: Session = Depends(get_db),
) -> PaginatedEventsResponse:
    """
    Lista eventos agrupados com paginação e filtro por tema.
    Popula automaticamente o evento de demonstração sintético caso o banco esteja vazio.
    """
    ensure_demo_seed(db)

    query = db.query(Event)
    chosen_theme = theme or tema
    if chosen_theme:
        query = query.filter(Event.tema == chosen_theme)

    total = query.count()
    events = (
        query.order_by(Event.periodo_fim.desc(), Event.criado_em.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return PaginatedEventsResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_to_event_summary(ev) for ev in events],
    )


@router.get("/{event_id}", response_model=EventDetailOut)
def get_event_detail(
    event_id: str,
    db: Session = Depends(get_db),
) -> EventDetailOut:
    """Retorna o evento, matérias vinculadas e dossiê de análise (se existir)."""
    ensure_demo_seed(db)
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evento '{event_id}' não encontrado.",
        )

    summary = _to_event_summary(event)
    dossier = build_verified_dossier_for_event(db, event)
    articles_out = [ArticleSummaryOut.model_validate(a) for a in event.articles]

    return EventDetailOut(
        **summary.model_dump(),
        articles=articles_out,
        dossier=dossier,
    )


@router.get("/{event_id}/analysis-status", response_model=AnalysisStatusResponse)
def get_analysis_status_route(
    event_id: str,
    db: Session = Depends(get_db),
) -> AnalysisStatusResponse:
    """Retorna o status atual do job assíncrono de análise do evento."""
    ensure_demo_seed(db)
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evento '{event_id}' não encontrado.",
        )
    return get_event_analysis_status(db, event_id=event.id)
