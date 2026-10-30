import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utcnow() -> datetime:
    """Retorna datetime UTC atual."""
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """Gera identificador UUID4 em string."""
    return str(uuid.uuid4())


VALID_THEMES = (
    "economia",
    "trabalho",
    "terra_e_agronegocio",
    "politica_institucional",
    "seguranca_e_estado",
    "politica_externa",
    "meio_ambiente",
    "cultura",
    "saude_educacao",
    "outros",
)

VALID_COLLECTION_METHODS = (
    "rss_full",
    "rss_summary",
    "trafilatura",
)


class Source(Base):
    """Fonte de notícias RSS/Atom cadastrada no sistema."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    url_rss: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    categoria_editorial: Mapped[str] = mapped_column(String(100), nullable=False)
    pais: Mapped[str] = mapped_column(String(16), nullable=False)
    idioma: Mapped[str] = mapped_column(String(16), nullable=False)
    posicao_editorial_declarada: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    etag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ultima_coleta: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    articles: Mapped[List["Article"]] = relationship(
        "Article",
        back_populates="source_rel",
        cascade="all, delete-orphan",
    )


class Event(Base):
    """Acontecimento agrupado a partir de matérias sobre o mesmo fato."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_uuid)
    titulo_provisorio: Mapped[str] = mapped_column(String(512), nullable=False)
    resumo: Mapped[str] = mapped_column(Text, nullable=False)
    periodo_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    periodo_fim: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    score_coesao: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    tema: Mapped[str] = mapped_column(String(64), nullable=False, default="outros", index=True)
    local: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    articles: Mapped[List["Article"]] = relationship(
        "Article",
        back_populates="event_rel",
    )
    bias_analyses: Mapped[List["ArticleBiasAnalysis"]] = relationship(
        "ArticleBiasAnalysis",
        back_populates="event_rel",
        cascade="all, delete-orphan",
    )
    event_analysis: Mapped[Optional["EventAnalysis"]] = relationship(
        "EventAnalysis",
        back_populates="event_rel",
        uselist=False,
        cascade="all, delete-orphan",
    )
    analysis_jobs: Mapped[List["AnalysisJob"]] = relationship(
        "AnalysisJob",
        back_populates="event_rel",
        cascade="all, delete-orphan",
    )


class Article(Base):
    """Matéria jornalística coletada via RSS ou extração HTML."""

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_uuid)
    source_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    titulo: Mapped[str] = mapped_column(String(512), nullable=False)
    url_canonica: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True, index=True)
    guid: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    veiculo: Mapped[str] = mapped_column(String(255), nullable=False)
    autor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    data_publicacao: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    data_coleta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    texto_limpo: Mapped[str] = mapped_column(Text, nullable=False)
    resumo: Mapped[str] = mapped_column(Text, nullable=False)
    idioma: Mapped[str] = mapped_column(String(16), nullable=False, default="pt")
    hash_conteudo: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metodo_coleta: Mapped[str] = mapped_column(String(32), nullable=False, default="rss_summary")
    metadados: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    embedding_blob: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    entidades_extraidas: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source_rel: Mapped["Source"] = relationship("Source", back_populates="articles")
    event_rel: Mapped[Optional["Event"]] = relationship("Event", back_populates="articles")
    bias_analyses: Mapped[List["ArticleBiasAnalysis"]] = relationship(
        "ArticleBiasAnalysis",
        back_populates="article_rel",
        cascade="all, delete-orphan",
    )


class ArticleBiasAnalysis(Base):
    """Análise de enquadramento e viés individual de uma matéria (Etapa 3.1)."""

    __tablename__ = "article_bias_analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_uuid)
    article_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    verified_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    modelo_llm: Mapped[str] = mapped_column(String(255), nullable=False)
    num_ctx: Mapped[int] = mapped_column(Integer, nullable=False, default=8192)
    tempo_execucao_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    article_rel: Mapped["Article"] = relationship("Article", back_populates="bias_analyses")
    event_rel: Mapped[Optional["Event"]] = relationship("Event", back_populates="bias_analyses")


class EventAnalysis(Base):
    """Dossiê de Contradição consolidado de um evento (Etapas 3.2 e 3.3)."""

    __tablename__ = "event_analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    dossier_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    modelo_llm: Mapped[str] = mapped_column(String(255), nullable=False)
    num_ctx: Mapped[int] = mapped_column(Integer, nullable=False, default=8192)
    tempo_execucao_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    event_rel: Mapped["Event"] = relationship("Event", back_populates="event_analysis")


class AnalysisJob(Base):
    """Job assíncrono e retomável de análise de um evento."""

    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_uuid)
    event_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    articles_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    articles_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_article_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    completed_article_ids: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modelo_llm: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    num_ctx: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    event_rel: Mapped["Event"] = relationship("Event", back_populates="analysis_jobs")


class PresentationDeck(Base):
    """Roteiro de apresentação para Modo Estúdio (ensaios) e Modo Live (OBS)."""

    __tablename__ = "presentation_decks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_uuid)
    titulo: Mapped[str] = mapped_column(String(512), nullable=False)
    modo: Mapped[str] = mapped_column(String(32), nullable=False, default="ensaio", index=True)
    event_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kpis: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    slides: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    charts: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    ticker_items: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )
