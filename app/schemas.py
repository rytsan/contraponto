import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


ThemeLiteral = Literal[
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
]

CollectionMethodLiteral = Literal[
    "rss_full",
    "rss_summary",
    "trafilatura",
]

ActorTypeLiteral = Literal[
    "trabalhador",
    "empresa",
    "estado",
    "veiculo",
    "sindicato",
    "movimento_popular",
    "instituicao",
    "outro",
]

RelationTypeLiteral = Literal[
    "controla",
    "financia",
    "cita",
    "enquadra",
    "resiste",
    "regula",
    "reprime",
    "lucra",
    "organiza",
]

VisualizationTypeLiteral = Literal[
    "bar",
    "line",
    "radar",
    "timeline",
]


class SourceBase(BaseModel):
    """Schema base de uma fonte RSS/Atom."""

    id: str = Field(..., min_length=1, max_length=100)
    nome: str = Field(..., min_length=1, max_length=255)
    url_rss: str = Field(..., min_length=5, max_length=1024)
    categoria_editorial: str = Field(..., min_length=1, max_length=100)
    pais: str = Field(..., min_length=1, max_length=16)
    idioma: str = Field(..., min_length=1, max_length=16)
    posicao_editorial_declarada: str = Field(..., min_length=1)
    descricao: str = Field(..., min_length=1)


class SourceCreate(SourceBase):
    """Payload para cadastro de nova fonte RSS via POST /sources."""
    pass


class SourceOut(SourceBase):
    """Representação de saída de uma fonte RSS."""

    model_config = ConfigDict(from_attributes=True)

    ultima_coleta: Optional[datetime] = None
    ativo: bool = True
    is_demo: bool = False


class SourceCheckItem(BaseModel):
    """Resultado individual da verificação de uma fonte via sources_loader --check."""

    id: str
    nome: str
    url_rss: str
    pending_verification_comment: bool = False
    valid_schema: bool = True
    reachable: bool = False
    status_code: Optional[int] = None
    entries_count: int = 0
    error: Optional[str] = None


class CoordinatesSchema(BaseModel):
    """Coordenadas geográficas opcionais de um evento."""

    lat: Optional[float] = None
    lon: Optional[float] = None


class EvidenceQuoteLLM(BaseModel):
    """Trecho citado extraído pelo LLM (sem o campo verified, que é calculado na Etapa 3.3)."""

    model_config = ConfigDict(extra="forbid")

    quote: str = Field(..., min_length=1)
    context: str = Field(..., min_length=1)


class EvidenceQuoteSchema(BaseModel):
    """Trecho citado com flag programática de verificação (Etapa 3.3)."""

    model_config = ConfigDict(extra="forbid")

    quote: str = Field(..., min_length=1)
    context: str = Field(..., min_length=1)
    verified: bool = Field(default=False)


class BiasAnalysisLLMOutput(BaseModel):
    """Retorno estruturado da Etapa 3.1 (análise de viés por matéria pelo LLM)."""

    model_config = ConfigDict(extra="forbid")

    central_thesis: str = Field(..., min_length=1)
    valued_actors: List[str] = Field(default_factory=list)
    devalued_actors: List[str] = Field(default_factory=list)
    ideological_vocabulary: List[str] = Field(default_factory=list)
    privileged_sources: List[str] = Field(default_factory=list)
    likely_omissions: List[str] = Field(default_factory=list)
    state_framing: str = Field(..., min_length=1)
    market_framing: str = Field(..., min_length=1)
    labor_framing: str = Field(..., min_length=1)
    protest_framing: str = Field(..., min_length=1)
    political_effect: str = Field(..., min_length=1)
    evidence_quotes: List[EvidenceQuoteLLM] = Field(..., min_length=1)


class CoveragePairSchema(BaseModel):
    """Cobertura analisada e verificada dentro do Dossiê Consolidado."""

    model_config = ConfigDict(extra="forbid")

    article_id: str
    source: str
    source_position: str
    url: str
    headline: str
    central_thesis: str
    valued_actors: List[str]
    devalued_actors: List[str]
    ideological_vocabulary: List[str]
    privileged_sources: List[str]
    likely_omissions: List[str]
    state_framing: str
    market_framing: str
    labor_framing: str
    protest_framing: str
    political_effect: str
    evidence_quotes: List[EvidenceQuoteSchema]


class ActorRelationSchema(BaseModel):
    """Relação direcionada entre dois atores no Grafo de Poder."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(..., min_length=1)
    relation: RelationTypeLiteral
    evidence: str = Field(..., min_length=1)


class ActorSchema(BaseModel):
    """Nó do grafo de atores com interesses materiais e relações."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    type: ActorTypeLiteral
    role: str = Field(..., min_length=1)
    material_interest: str = Field(..., min_length=1)
    relations: List[ActorRelationSchema] = Field(default_factory=list)


class MarxistLeninistAnalysisSchema(BaseModel):
    """Bloco estruturado da análise marxista-leninista e materialista histórica."""

    model_config = ConfigDict(extra="forbid")

    central_contradiction: str = Field(..., min_length=1)
    class_relations: str = Field(..., min_length=1)
    property_and_power: str = Field(..., min_length=1)
    role_of_state: str = Field(..., min_length=1)
    imperialism_or_dependency: str = Field(..., min_length=1)
    ideology_and_naturalization: str = Field(..., min_length=1)
    hegemony_and_silenced_voices: str = Field(..., min_length=1)
    forms_of_struggle: str = Field(..., min_length=1)
    immediate_demand: str = Field(..., min_length=1)
    strategic_perspective: str = Field(..., min_length=1)
    limitations_and_uncertainty: List[str] = Field(default_factory=list)


class DataVisualizationSchema(BaseModel):
    """Gráfico estruturado baseado exclusivamente em artigos reais do evento."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    type: VisualizationTypeLiteral
    description: str = Field(..., min_length=1)
    labels: List[str] = Field(default_factory=list)
    values: List[float] = Field(default_factory=list)
    source_article_ids: List[str] = Field(default_factory=list)


class EventConsolidationLLMOutput(BaseModel):
    """Retorno estruturado da Etapa 3.2 (consolidação marxista-leninista pelo LLM)."""

    model_config = ConfigDict(extra="forbid")

    factual_anchor: str = Field(..., min_length=1)
    actors: List[ActorSchema] = Field(default_factory=list)
    marxist_leninist_analysis: MarxistLeninistAnalysisSchema
    reader_questions: List[str] = Field(..., min_length=1)
    data_visualizations: List[DataVisualizationSchema] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DossierMetadataArticleItem(BaseModel):
    """Metadados completos de auditoria de cada artigo usado no dossiê (Cena 6)."""

    id: str
    source_id: str
    veiculo: str
    autor: Optional[str] = None
    data_publicacao: Optional[datetime] = None
    data_coleta: datetime
    url_canonica: str
    titulo: str
    posicao_editorial_declarada: str
    categoria_editorial: str = ""
    metodo_coleta: str
    is_demo: bool = False


class DossierAuditMetadata(BaseModel):
    """Metadados de auditoria da execução da análise."""

    analyzed_at: datetime
    llm_model: str
    num_ctx: int
    execution_time_ms: int = 0
    is_demo: bool = False
    articles_registry: List[DossierMetadataArticleItem] = Field(default_factory=list)


class DossierSchema(BaseModel):
    """Contrato completo do Dossiê de Contradição Consolidado."""

    event_id: str
    title: Optional[str] = None
    is_demo: bool = False
    factual_anchor: str
    theme: str
    location: Optional[str] = None
    coordinates: CoordinatesSchema
    coverage_pairs: List[CoveragePairSchema]
    actors: List[ActorSchema]
    marxist_leninist_analysis: MarxistLeninistAnalysisSchema
    reader_questions: List[str]
    data_visualizations: List[DataVisualizationSchema]
    confidence: float = Field(..., ge=0.0, le=1.0)
    audit_metadata: Optional[DossierAuditMetadata] = None


class ArticleSummaryOut(BaseModel):
    """Resumo de artigo para listagens paginadas."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    event_id: Optional[str] = None
    titulo: str
    url_canonica: str
    veiculo: str
    autor: Optional[str] = None
    data_publicacao: Optional[datetime] = None
    data_coleta: datetime
    resumo: str
    idioma: str
    metodo_coleta: str
    is_demo: bool = False


class ArticleOut(ArticleSummaryOut):
    """Artigo completo incluindo texto limpo e metadados."""

    guid: str
    texto_limpo: str
    hash_conteudo: str
    metadados: Dict[str, Any] = Field(default_factory=dict)
    embedding_model: Optional[str] = None
    entidades_extraidas: Optional[Dict[str, Any]] = None


class EventSummaryOut(BaseModel):
    """Resumo de evento para listagem GET /events."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    titulo_provisorio: str
    resumo: str
    periodo_inicio: datetime
    periodo_fim: datetime
    score_coesao: float
    tema: str
    local: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    is_demo: bool = False
    articles_count: int = 0
    has_dossier: bool = False
    confidence: Optional[float] = None


class EventDetailOut(EventSummaryOut):
    """Detalhes completos de um evento em GET /events/{id}."""

    articles: List[ArticleSummaryOut] = Field(default_factory=list)
    dossier: Optional[DossierSchema] = None


class AnalyzeTriggerResponse(BaseModel):
    """Resposta imediata (HTTP 202) ao enfileirar job de análise."""

    analysis_id: str
    status: Literal["queued", "running", "completed", "failed"]


class AnalysisStatusResponse(BaseModel):
    """Resposta do endpoint GET /events/{id}/analysis-status."""

    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    articles_done: int
    articles_total: int
    error: Optional[str] = None


class PaginatedArticlesResponse(BaseModel):
    """Lista paginada de artigos."""

    total: int
    limit: int
    offset: int
    items: List[ArticleSummaryOut]


class PaginatedEventsResponse(BaseModel):
    """Lista paginada de eventos."""

    total: int
    limit: int
    offset: int
    items: List[EventSummaryOut]


class HealthResponse(BaseModel):
    """Status detalhado de saúde do sistema (GET /health)."""

    status: str
    database: str
    llama_server: Dict[str, Any]
    qdrant: Dict[str, Any]
    scheduler: Dict[str, Any]
    sources_last_collection: Dict[str, Optional[str]]


DeckModeLiteral = Literal["ensaio", "live"]

_SAFE_COLOR_RE = re.compile(r"^(var\(--[a-zA-Z0-9_-]+\)|#[0-9a-fA-F]{3,8}|crimson|amber|cyan|dim|lime|white)$")
_SAFE_HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _sanitize_css_color(val: str, default: str = "var(--amber)") -> str:
    cleaned = (val or "").strip()
    return cleaned if _SAFE_COLOR_RE.match(cleaned) else default


class DeckKPI(BaseModel):
    """Indicador superior da barra de broadcast."""

    label: str = Field(default="", max_length=120)
    value: str = Field(default="", max_length=120)
    color: str = Field(default="var(--amber)", max_length=64)

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        return _sanitize_css_color(v, "var(--amber)")


class DeckSlideLink(BaseModel):
    """Link de fonte exibido na coluna lateral do slide."""

    label: str = Field(default="", max_length=200)
    url: str = Field(default="", max_length=1024)

    @field_validator("url")
    @classmethod
    def validate_http_url(cls, v: str) -> str:
        cleaned = (v or "").strip()
        if not cleaned or cleaned in ("https://", "http://"):
            return ""
        if not _SAFE_HTTP_URL_RE.match(cleaned):
            raise ValueError("URL do link deve usar http:// ou https://")
        return cleaned


class DeckSlide(BaseModel):
    """Slide/capítulo individual do Modo Estúdio e Modo Live."""

    shortDate: str = Field(default="Capítulo", max_length=60)
    timestamp: str = Field(default="", max_length=160)
    title: str = Field(default="Sem título", max_length=512)
    summary: str = Field(default="")
    summary2: str = Field(default="")
    deep: str = Field(default="")
    code: str = Field(default="")
    nuance_notes: str = Field(default="")
    metricLabel: str = Field(default="INDICADOR CHAVE", max_length=120)
    metricVal: str = Field(default="—", max_length=80)
    metricColor: str = Field(default="var(--amber)", max_length=64)
    metricSub: str = Field(default="")
    specs: List[List[str]] = Field(default_factory=list)
    links: List[DeckSlideLink] = Field(default_factory=list)

    @field_validator("metricColor")
    @classmethod
    def validate_metric_color(cls, v: str) -> str:
        return _sanitize_css_color(v, "var(--amber)")


class DeckChartRow(BaseModel):
    """Barra comparativa dentro de um card do painel gráfico [G]."""

    label: str = Field(default="", max_length=160)
    pct: float = Field(default=50.0, ge=0.0, le=100.0)
    displayValue: str = Field(default="", max_length=80)
    color: str = Field(default="amber", max_length=64)

    @field_validator("color")
    @classmethod
    def validate_row_color(cls, v: str) -> str:
        return _sanitize_css_color(v, "amber")


class DeckChartCard(BaseModel):
    """Coluna do overlay de 3 composições gráficas [G]."""

    title: str = Field(default="", max_length=200)
    subtitle: str = Field(default="")
    rows: List[DeckChartRow] = Field(default_factory=list)
    footerTitle: str = Field(default="")
    footerText: str = Field(default="")


class DeckCreateUpdate(BaseModel):
    """Payload de criação ou atualização de um ensaio ou pauta ao vivo."""

    titulo: str = Field(default="Roteiro sem título", max_length=512)
    modo: DeckModeLiteral = "ensaio"
    event_id: Optional[str] = None
    kpis: List[DeckKPI] = Field(default_factory=list)
    slides: List[DeckSlide] = Field(default_factory=list)
    charts: List[DeckChartCard] = Field(default_factory=list)
    ticker_items: List[str] = Field(default_factory=list)


class DeckSummaryOut(BaseModel):
    """Resumo de pauta/ensaio na listagem."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    titulo: str
    modo: str
    event_id: Optional[str] = None
    slides_count: int = 0
    is_demo: bool = False
    criado_em: datetime
    atualizado_em: datetime


class DeckOut(BaseModel):
    """Pauta/ensaio completo para renderização no Estúdio ou Live."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    titulo: str
    modo: str
    event_id: Optional[str] = None
    kpis: List[DeckKPI] = Field(default_factory=list)
    slides: List[DeckSlide] = Field(default_factory=list)
    charts: List[DeckChartCard] = Field(default_factory=list)
    ticker_items: List[str] = Field(default_factory=list)
    is_demo: bool = False
    criado_em: datetime
    atualizado_em: datetime


class NuanceSuggestRequest(BaseModel):
    """Entrada para geração/refinamento de nuance de ensaio via llama-server."""

    deck_title: str = Field(default="", max_length=512)
    slide: DeckSlide
    angle_hint: str = Field(default="", max_length=400)


class NuanceSuggestLLMOutput(BaseModel):
    """Saída estruturada do LLM para refinar um capítulo do vídeo-ensaio."""

    model_config = ConfigDict(extra="forbid")

    nuance_notes: str = Field(..., min_length=1)
    summary2: str = Field(..., min_length=1)
    deep: str = Field(..., min_length=1)
