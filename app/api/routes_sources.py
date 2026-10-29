from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Source
from app.schemas import SourceCreate, SourceOut
from app.collectors.sources_loader import append_source_to_yaml, sync_sources_to_db

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=List[SourceOut])
def list_sources(db: Session = Depends(get_db)) -> List[Source]:
    """Lista todas as fontes RSS cadastradas (sincronizando data/sources.yaml se necessário)."""
    real_count = db.query(Source).filter(Source.is_demo.is_(False)).count()
    if real_count == 0:
        try:
            sync_sources_to_db(db)
        except Exception:
            pass
    return db.query(Source).order_by(Source.is_demo.asc(), Source.nome.asc()).all()


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(
    source_in: SourceCreate,
    db: Session = Depends(get_db),
) -> Source:
    """Adiciona uma nova fonte RSS persistindo simultaneamente no banco SQLite e em sources.yaml."""
    existing = (
        db.query(Source)
        .filter(or_(Source.id == source_in.id, Source.url_rss == source_in.url_rss))
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Fonte com id '{source_in.id}' ou URL '{source_in.url_rss}' já cadastrada.",
        )

    new_source = Source(
        id=source_in.id,
        nome=source_in.nome,
        url_rss=source_in.url_rss,
        categoria_editorial=source_in.categoria_editorial,
        pais=source_in.pais,
        idioma=source_in.idioma,
        posicao_editorial_declarada=source_in.posicao_editorial_declarada,
        descricao=source_in.descricao,
        ativo=True,
        is_demo=False,
    )
    db.add(new_source)
    db.commit()
    db.refresh(new_source)

    try:
        append_source_to_yaml(source_in)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fonte salva no banco, mas houve erro ao atualizar sources.yaml: {exc}",
        ) from exc

    return new_source
