from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Article, Event
from app.schemas import ArticleOut, ArticleSummaryOut, PaginatedArticlesResponse

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=PaginatedArticlesResponse)
def list_articles(
    source: Optional[str] = Query(default=None, description="Filtrar por ID da fonte ou nome do veículo"),
    theme: Optional[str] = Query(default=None, description="Filtrar por tema do evento vinculado"),
    event_id: Optional[str] = Query(default=None, description="Filtrar por ID do evento"),
    start_date: Optional[datetime] = Query(default=None, description="Data inicial de publicação (ISO 8601)"),
    end_date: Optional[datetime] = Query(default=None, description="Data final de publicação (ISO 8601)"),
    limit: int = Query(default=20, ge=1, le=100, description="Itens por página (padrão 20, máx 100)"),
    offset: int = Query(default=0, ge=0, description="Deslocamento da paginação"),
    db: Session = Depends(get_db),
) -> PaginatedArticlesResponse:
    """Lista artigos com filtros por fonte, tema, período e evento, com paginação."""
    query = db.query(Article)

    if source:
        query = query.filter((Article.source_id == source) | (Article.veiculo.ilike(f"%{source}%")))

    if event_id:
        query = query.filter(Article.event_id == event_id)

    if theme:
        query = query.join(Event, Article.event_id == Event.id).filter(Event.tema == theme)

    if start_date:
        query = query.filter(Article.data_publicacao >= start_date)

    if end_date:
        query = query.filter(Article.data_publicacao <= end_date)

    total = query.count()
    items = (
        query.order_by(Article.data_publicacao.desc().nullslast(), Article.data_coleta.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return PaginatedArticlesResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[ArticleSummaryOut.model_validate(item) for item in items],
    )


@router.get("/{article_id}", response_model=ArticleOut)
def get_article(
    article_id: str,
    db: Session = Depends(get_db),
) -> ArticleOut:
    """Retorna um artigo completo pelo seu ID."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artigo '{article_id}' não encontrado.",
        )
    return ArticleOut.model_validate(article)
