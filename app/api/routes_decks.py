import html as html_lib
import json
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, Query, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Article, Event, PresentationDeck, Source, utcnow
from app.schemas import (
    DeckChartCard,
    DeckChartRow,
    DeckCreateUpdate,
    DeckKPI,
    DeckOut,
    DeckSlide,
    DeckSlideLink,
    DeckSummaryOut,
    NuanceSuggestLLMOutput,
    NuanceSuggestRequest,
)
from app.analysis.llm_client import LlamaCppClient
from app.api.routes_analysis import get_llm_client
from app.api.routes_events import build_verified_dossier_for_event, ensure_demo_seed
from app.scheduler import run_collection_and_clustering_cycle

router = APIRouter(prefix="/decks", tags=["decks"])

_live_ws_clients: Set[WebSocket] = set()
_last_live_sync: Optional[Dict[str, Any]] = None

NUANCE_JSON_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["nuance_notes", "summary2", "deep"],
    "properties": {
        "nuance_notes": {"type": "string", "minLength": 1},
        "summary2": {"type": "string", "minLength": 1},
        "deep": {"type": "string", "minLength": 1},
    },
}


def _to_summary(deck: PresentationDeck) -> DeckSummaryOut:
    return DeckSummaryOut(
        id=deck.id,
        titulo=deck.titulo,
        modo=deck.modo,
        event_id=deck.event_id,
        slides_count=len(deck.slides or []),
        is_demo=deck.is_demo,
        criado_em=deck.criado_em,
        atualizado_em=deck.atualizado_em,
    )


def _truncate(text: str, max_len: int) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= max_len else clean[: max_len - 1].rstrip() + "…"


def _resolve_valid_event_id(db: Session, event_id: Optional[str]) -> Optional[str]:
    if not event_id:
        return None
    exists = db.query(Event.id).filter(Event.id == event_id).first()
    return event_id if exists else None


def _build_essay_payload_from_event(db: Session, event: Event) -> DeckCreateUpdate:
    dossier = build_verified_dossier_for_event(db, event)
    articles = list(event.articles or [])
    slides: List[DeckSlide] = []

    if dossier:
        conf_pct = f"{round(dossier.confidence * 100)}%"
        kpis = [
            DeckKPI(label="Tema:", value=dossier.theme.replace("_", " ").upper(), color="var(--crimson)"),
            DeckKPI(label="Coberturas:", value=f"{len(dossier.coverage_pairs)} veículos", color="var(--amber)"),
            DeckKPI(label="Citações Verificadas:", value=conf_pct, color="var(--cyan)"),
            DeckKPI(label="Atores Mapeados:", value=str(len(dossier.actors)), color="var(--lime)"),
        ]

        top_links = [
            DeckSlideLink(label=_truncate(f"{a.veiculo} // {a.titulo}", 64), url=a.url_canonica)
            for a in articles[:3]
        ]

        slides.append(
            DeckSlide(
                shortDate="01. Fato",
                timestamp=_truncate(f"{event.local or 'Panorama'} // Âncora Factual", 150),
                title=_truncate(dossier.title or event.titulo_provisorio, 160),
                summary=dossier.factual_anchor,
                summary2=dossier.marxist_leninist_analysis.central_contradiction,
                deep=dossier.marxist_leninist_analysis.property_and_power,
                code=f"Confiança textual verificada: {conf_pct} ({len(articles)} matérias cruzadas)",
                nuance_notes=(
                    "ABERTURA DO ENSAIO: Apresentar primeiro apenas o núcleo factual incontestável antes de revelar "
                    "como cada veículo recorta o conflito. Destacar quem financia e quem trabalha."
                ),
                metricLabel="CONFIANÇA VERIFICADA",
                metricVal=conf_pct,
                metricColor="var(--cyan)",
                metricSub="Proporção de citações confirmadas literalmente nos textos-fonte das matérias.",
                specs=[
                    ["Tema", dossier.theme],
                    ["Local", event.local or "Não especificado"],
                    ["Coesão do agrupamento", f"{round((event.score_coesao or 0) * 100)}%"],
                    ["Veículos confrontados", str(len(dossier.coverage_pairs))],
                ],
                links=top_links,
            )
        )

        palette = ["var(--amber)", "var(--lime)", "var(--cyan)", "var(--crimson)"]
        for idx, cov in enumerate(dossier.coverage_pairs[:6], start=2):
            verified_quotes = [q for q in cov.evidence_quotes if q.verified]
            chosen_quote = verified_quotes[0] if verified_quotes else (cov.evidence_quotes[0] if cov.evidence_quotes else None)
            short_source = cov.source.split("—")[0].strip()
            omissions_str = "; ".join(cov.likely_omissions[:2]) or "Sem omissões destacadas"
            vocab_str = ", ".join(cov.ideological_vocabulary[:4]) or "—"

            slides.append(
                DeckSlide(
                    shortDate=_truncate(f"{idx:02d}. {short_source}", 18),
                    timestamp=_truncate(cov.source_position, 90),
                    title=_truncate(cov.headline, 160),
                    summary=cov.central_thesis,
                    summary2=f"Efeito político: {cov.political_effect}",
                    deep=(
                        f"Omissões prováveis neste recorte: {omissions_str}. "
                        f"Enquadramento do Estado: {cov.state_framing}"
                    ),
                    code=(
                        f"Citação {'[VERIFICADA]' if chosen_quote and chosen_quote.verified else '[TRECHO]'}: "
                        f"\"{_truncate(chosen_quote.quote, 220)}\""
                        if chosen_quote
                        else f"Vocabulário-chave: {vocab_str}"
                    ),
                    nuance_notes=(
                        f"NUANCE ({short_source}): Observar as palavras '{vocab_str}'. "
                        f"Valoriza: {', '.join(cov.valued_actors[:2]) or '—'}. "
                        f"Silencia/omite: {omissions_str}."
                    ),
                    metricLabel="FONTES PRIVILEGIADAS",
                    metricVal=f"{len(cov.privileged_sources)} vozes",
                    metricColor=palette[(idx - 2) % len(palette)],
                    metricSub=_truncate(", ".join(cov.privileged_sources[:3]) or cov.source, 110),
                    specs=[
                        ["Valoriza", _truncate(", ".join(cov.valued_actors[:2]) or "—", 42)],
                        ["Desvaloriza", _truncate(", ".join(cov.devalued_actors[:2]) or "—", 42)],
                        ["Léxico ideológico", _truncate(vocab_str, 42)],
                        ["Citações verificadas", f"{len(verified_quotes)}/{len(cov.evidence_quotes)}"],
                    ],
                    links=[DeckSlideLink(label=_truncate(short_source, 56), url=cov.url)],
                )
            )

        if dossier.actors:
            next_num = len(slides) + 1
            lead_actors = dossier.actors[:4]
            slides.append(
                DeckSlide(
                    shortDate=f"{next_num:02d}. Atores",
                    timestamp="Mapa de Interesses Materiais",
                    title="Quem ganha, quem perde e quem arbitra o conflito",
                    summary=" ".join(f"{a.name}: {a.material_interest}." for a in lead_actors[:2]),
                    summary2=" ".join(f"{a.name}: {a.material_interest}." for a in lead_actors[2:4])
                    or dossier.marxist_leninist_analysis.class_relations,
                    deep=dossier.marxist_leninist_analysis.role_of_state,
                    code=f"Formas de luta identificadas: {_truncate(dossier.marxist_leninist_analysis.forms_of_struggle, 200)}",
                    nuance_notes=(
                        "TRANSIÇÃO DO ENSAIO: Sair da superfície retórica das manchetes e mostrar a base material "
                        "(orçamento, lucro, salário, propriedade e aparato estatal)."
                    ),
                    metricLabel="ATORES EM DISPUTA",
                    metricVal=f"{len(dossier.actors)} polos",
                    metricColor="var(--crimson)",
                    metricSub="Sujeitos políticos, econômicos e estatais extraídos das matérias.",
                    specs=[[a.name[:24], _truncate(a.role, 38)] for a in lead_actors],
                    links=top_links[:2],
                )
            )

        final_num = len(slides) + 1
        q_list = dossier.reader_questions or []
        slides.append(
            DeckSlide(
                shortDate=f"{final_num:02d}. Síntese",
                timestamp="Fechamento do Ensaio // Questões de Fundo",
                title="Hegemonia, vozes silenciadas e perspectiva estrutural",
                summary=dossier.marxist_leninist_analysis.hegemony_and_silenced_voices,
                summary2=dossier.marxist_leninist_analysis.strategic_perspective,
                deep=dossier.marxist_leninist_analysis.ideology_and_naturalization,
                code=_truncate(q_list[0], 240) if q_list else dossier.marxist_leninist_analysis.immediate_demand,
                nuance_notes=(
                    "FECHAMENTO: Deixar a pergunta crítica no ar para o público comentar na live/vídeo: "
                    + (q_list[0] if q_list else dossier.marxist_leninist_analysis.immediate_demand)
                ),
                metricLabel="DEMANDA IMEDIATA",
                metricVal="Síntese",
                metricColor="var(--amber)",
                metricSub=_truncate(dossier.marxist_leninist_analysis.immediate_demand, 120),
                specs=[
                    [f"Pergunta {i + 1}", _truncate(q, 44)]
                    for i, q in enumerate(q_list[:3])
                ],
                links=top_links[:2],
            )
        )

        charts: List[DeckChartCard] = []
        bar_colors = ["crimson", "amber", "cyan", "dim"]
        for viz in dossier.data_visualizations[:2]:
            max_val = max(viz.values) if viz.values and max(viz.values) > 0 else 1.0
            rows = [
                DeckChartRow(
                    label=_truncate(lbl, 28),
                    pct=round(min(100.0, max(4.0, (val / max_val) * 100.0)), 1),
                    displayValue=f"{val:g}",
                    color=bar_colors[i % len(bar_colors)],
                )
                for i, (lbl, val) in enumerate(zip(viz.labels, viz.values))
            ]
            charts.append(
                DeckChartCard(
                    title=_truncate(viz.title, 180),
                    subtitle=viz.description,
                    rows=rows,
                    footerTitle="Auditoria de Dados",
                    footerText=f"Extraído de {len(viz.source_article_ids)} matéria(s) vinculada(s) ao dossiê.",
                )
            )

        cov_rows = [
            DeckChartRow(
                label=_truncate(c.source.split("—")[0].strip(), 26),
                pct=min(100.0, max(15.0, len(c.privileged_sources) * 25.0)),
                displayValue=f"{len(c.privileged_sources)} fontes",
                color=bar_colors[i % len(bar_colors)],
            )
            for i, c in enumerate(dossier.coverage_pairs[:5])
        ]
        charts.append(
            DeckChartCard(
                title="Vozes & Omissões por Veículo",
                subtitle="Comparativo de fontes privilegiadas acionadas em cada cobertura analisada:",
                rows=cov_rows,
                footerTitle="Confiança Geral do Dossiê",
                footerText=f"{conf_pct} dos trechos citados foram verificados literalmente nos textos-fonte.",
            )
        )
        ticker_items = [f"[{a.veiculo}] {a.titulo}" for a in articles]
        return DeckCreateUpdate(
            titulo=f"Ensaio: {_truncate(dossier.title or event.titulo_provisorio, 120)}",
            modo="ensaio",
            event_id=event.id,
            kpis=kpis,
            slides=slides,
            charts=charts[:3],
            ticker_items=ticker_items,
        )

    # Fallback quando o evento ainda não passou pelo LLM (usa matérias brutas do RSS)
    kpis = [
        DeckKPI(label="Tema:", value=event.tema.upper(), color="var(--amber)"),
        DeckKPI(label="Matérias:", value=str(len(articles)), color="var(--cyan)"),
        DeckKPI(label="Coesão:", value=f"{round((event.score_coesao or 0) * 100)}%", color="var(--lime)"),
    ]
    for idx, art in enumerate(articles[:10], start=1):
        slides.append(
            DeckSlide(
                shortDate=_truncate(f"{idx:02d}. {art.veiculo}", 18),
                timestamp=(
                    art.data_publicacao.strftime("%d/%m/%Y %H:%M UTC")
                    if art.data_publicacao
                    else _truncate(art.veiculo, 150)
                ),
                title=_truncate(art.titulo, 500),
                summary=art.resumo,
                summary2=_truncate(art.texto_limpo, 340),
                deep=_truncate(art.texto_limpo, 700),
                code=f"Fonte: {_truncate(art.veiculo, 80)} ({art.metodo_coleta})",
                nuance_notes="Adicione aqui suas notas de nuance, ironias do enquadramento ou contexto histórico.",
                metricLabel="VEÍCULO",
                metricVal=_truncate(art.veiculo, 16),
                metricColor="var(--amber)",
                metricSub=f"Coleta via {art.metodo_coleta}",
                specs=[["Autor", art.autor or "Redação"], ["Idioma", art.idioma]],
                links=[DeckSlideLink(label=_truncate(f"Abrir em {art.veiculo}", 180), url=art.url_canonica)],
            )
        )
    if not slides:
        slides.append(
            DeckSlide(
                shortDate="01. Pauta",
                timestamp="Rascunho Inicial",
                title=_truncate(event.titulo_provisorio, 500),
                summary=event.resumo,
                nuance_notes="Escreva os pontos centrais do seu ensaio.",
            )
        )
    return DeckCreateUpdate(
        titulo=f"Ensaio: {_truncate(event.titulo_provisorio, 120)}",
        modo="ensaio",
        event_id=event.id,
        kpis=kpis,
        slides=slides,
        charts=[],
        ticker_items=[f"[{a.veiculo}] {a.titulo}" for a in articles],
    )


def _build_live_payload_from_feed(db: Session, limit: int = 10, theme: Optional[str] = None) -> DeckCreateUpdate:
    ensure_demo_seed(db)
    ev_query = db.query(Event).options(joinedload(Event.articles), joinedload(Event.event_analysis))
    if theme:
        ev_query = ev_query.filter(Event.tema == theme)
    events = ev_query.order_by(Event.periodo_fim.desc(), Event.criado_em.desc()).limit(limit).all()

    recent_articles = (
        db.query(Article)
        .order_by(Article.data_publicacao.desc().nullslast(), Article.data_coleta.desc())
        .limit(20)
        .all()
    )
    active_sources = db.query(Source).filter(Source.ativo.is_(True)).count()

    slides: List[DeckSlide] = []
    palette = ["var(--crimson)", "var(--amber)", "var(--cyan)", "var(--lime)"]

    for idx, ev in enumerate(events[:10], start=1):
        ev_articles = list(ev.articles or [])
        veiculos = list(dict.fromkeys(a.veiculo for a in ev_articles))
        dossier = build_verified_dossier_for_event(db, ev)
        lead_summary = dossier.factual_anchor if dossier else ev.resumo
        second_summary = (
            dossier.marxist_leninist_analysis.central_contradiction
            if dossier
            else (ev_articles[0].resumo if ev_articles else "")
        )
        deep_text = (
            " | ".join(f"{c.source.split('—')[0].strip()}: {c.central_thesis}" for c in dossier.coverage_pairs[:3])
            if dossier
            else (ev_articles[0].texto_limpo[:550] if ev_articles else ev.resumo)
        )

        slides.append(
            DeckSlide(
                shortDate=_truncate(f"{idx:02d}. {ev.tema.split('_')[0].capitalize()}", 18),
                timestamp=ev.periodo_fim.strftime("%d/%m %H:%M UTC") if ev.periodo_fim else ev.tema,
                title=_truncate((dossier.title if dossier else None) or ev.titulo_provisorio, 160),
                summary=lead_summary,
                summary2=second_summary,
                deep=deep_text,
                code=f"Cruzamento: {len(ev_articles)} matéria(s) em {len(veiculos)} veículo(s)",
                nuance_notes=(
                    f"PAUTA AO VIVO #{idx}: Destacar contraste entre {', '.join(veiculos[:3]) or 'as fontes'}."
                ),
                metricLabel="COBERTURAS AGRUPADAS",
                metricVal=f"{len(ev_articles)} fontes",
                metricColor=palette[(idx - 1) % len(palette)],
                metricSub=_truncate(", ".join(veiculos[:4]) or "Monitoramento RSS", 110),
                specs=[
                    ["Tema", ev.tema],
                    ["Local", ev.local or "Nacional / Internacional"],
                    ["Coesão", f"{round((ev.score_coesao or 0) * 100)}%"],
                    ["Dossiê Crítico", "Pronto" if dossier else "Pendente"],
                ],
                links=[
                    DeckSlideLink(label=_truncate(f"{a.veiculo}", 48), url=a.url_canonica)
                    for a in ev_articles[:3]
                ],
            )
        )

    theme_counts: Dict[str, int] = {}
    for ev in events:
        theme_counts[ev.tema] = theme_counts.get(ev.tema, 0) + max(1, len(ev.articles or []))
    max_tc = max(theme_counts.values()) if theme_counts else 1
    theme_rows = [
        DeckChartRow(
            label=t.replace("_", " ").capitalize(),
            pct=round((cnt / max_tc) * 100.0, 1),
            displayValue=f"{cnt} mat.",
            color=["crimson", "amber", "cyan", "dim"][i % 4],
        )
        for i, (t, cnt) in enumerate(sorted(theme_counts.items(), key=lambda x: -x[1])[:6])
    ]

    source_counts: Dict[str, int] = {}
    for a in recent_articles:
        source_counts[a.veiculo] = source_counts.get(a.veiculo, 0) + 1
    max_sc = max(source_counts.values()) if source_counts else 1
    source_rows = [
        DeckChartRow(
            label=_truncate(v, 24),
            pct=round((cnt / max_sc) * 100.0, 1),
            displayValue=f"{cnt}",
            color=["amber", "cyan", "crimson", "dim"][i % 4],
        )
        for i, (v, cnt) in enumerate(sorted(source_counts.items(), key=lambda x: -x[1])[:6])
    ]

    charts = [
        DeckChartCard(
            title="1. Volume por Eixo Temático",
            subtitle="Concentração de matérias nos acontecimentos em pauta nesta transmissão:",
            rows=theme_rows,
            footerTitle="Agregação Automática",
            footerText=f"{len(events)} acontecimentos selecionados no giro atual.",
        ),
        DeckChartCard(
            title="2. Veículos Mais Ativos no Giro",
            subtitle="Distribuição das últimas matérias capturadas pelos coletores RSS:",
            rows=source_rows,
            footerTitle="Fontes Ativas",
            footerText=f"{active_sources} feeds monitorados no Contraponto.",
        ),
        DeckChartCard(
            title="3. Coesão Semântica da Pauta",
            subtitle="Grau de convergência factual entre matérias agrupadas em cada nó da live:",
            rows=[
                DeckChartRow(
                    label=_truncate(ev.titulo_provisorio, 24),
                    pct=round(min(100.0, (ev.score_coesao or 0.8) * 100.0), 1),
                    displayValue=f"{round((ev.score_coesao or 0.8) * 100)}%",
                    color="cyan" if ev.event_analysis else "dim",
                )
                for ev in events[:5]
            ],
            footerTitle="Verificação",
            footerText="Barras em ciano indicam acontecimentos já com Dossiê de Contradição verificado.",
        ),
    ]

    now_str = utcnow().strftime("%d/%m %H:%M UTC")
    kpis = [
        DeckKPI(label="MODO:", value="AO VIVO // GIRO RSS", color="var(--crimson)"),
        DeckKPI(label="Pautas na Fila:", value=str(len(slides)), color="var(--amber)"),
        DeckKPI(label="Fontes Ativas:", value=str(active_sources), color="var(--cyan)"),
        DeckKPI(label="Atualizado:", value=now_str, color="var(--lime)"),
    ]
    ticker = [f"[{a.veiculo.split('—')[0].strip()}] {a.titulo}" for a in recent_articles[:15]]

    return DeckCreateUpdate(
        titulo=f"Giro Ao Vivo ({now_str})",
        modo="live",
        event_id=events[0].id if len(events) == 1 else None,
        kpis=kpis,
        slides=slides,
        charts=charts,
        ticker_items=ticker,
    )


def _persist_deck(db: Session, payload: DeckCreateUpdate, is_demo: bool = False) -> PresentationDeck:
    deck = PresentationDeck(
        titulo=payload.titulo.strip() or "Roteiro sem título",
        modo=payload.modo,
        event_id=_resolve_valid_event_id(db, payload.event_id),
        kpis=[k.model_dump() for k in payload.kpis],
        slides=[s.model_dump() for s in payload.slides],
        charts=[c.model_dump() for c in payload.charts],
        ticker_items=list(payload.ticker_items),
        is_demo=is_demo,
    )
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return deck


def ensure_default_deck(db: Session) -> None:
    if db.query(PresentationDeck).count() > 0:
        return
    ensure_demo_seed(db)
    first_event = db.query(Event).order_by(Event.periodo_fim.desc()).first()
    if first_event is not None:
        payload = _build_essay_payload_from_event(db, first_event)
        _persist_deck(db, payload, is_demo=first_event.is_demo)


@router.websocket("/ws/live")
async def websocket_live_sync(websocket: WebSocket) -> None:
    """Canal WebSocket para sincronizar o Modo Estúdio com o Browser Source do OBS em tempo real."""
    global _last_live_sync
    await websocket.accept()
    _live_ws_clients.add(websocket)
    if _last_live_sync is not None:
        try:
            await websocket.send_json(_last_live_sync)
        except Exception:
            pass
    try:
        while True:
            msg = await websocket.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "SYNC_STATE":
                _last_live_sync = msg
                dead: List[WebSocket] = []
                for peer in list(_live_ws_clients):
                    if peer is websocket:
                        continue
                    try:
                        await peer.send_json(msg)
                    except Exception:
                        dead.append(peer)
                for d in dead:
                    _live_ws_clients.discard(d)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _live_ws_clients.discard(websocket)


@router.post("/suggest-nuance", response_model=NuanceSuggestLLMOutput)
def suggest_slide_nuance(
    req: NuanceSuggestRequest,
    llm_client: LlamaCppClient = Depends(get_llm_client),
) -> NuanceSuggestLLMOutput:
    """Usa o llama-server local para sugerir/refinar notas de nuance, contraponto e aprofundamento."""
    prompt = (
        "Você é um roteirista de vídeo-ensaio investigativo e crítico de mídia.\n"
        f"Título geral do ensaio: {req.deck_title or 'Análise Crítica'}\n"
        f"Capítulo atual: {req.slide.shortDate} — {req.slide.title}\n"
        f"Resumo factual (parágrafo 1): {req.slide.summary}\n"
        f"Contraponto atual (parágrafo 2): {req.slide.summary2}\n"
        f"Detalhes da gaveta: {req.slide.deep}\n"
        f"Citação/destaque: {req.slide.code}\n"
        f"Nota atual do apresentador: {req.slide.nuance_notes}\n"
        f"Instrução extra de ângulo/tom: {req.angle_hint or 'Explicitar tensões materiais, omissões e transição fluida de fala.'}\n\n"
        "Retorne um JSON estrito com:\n"
        "- nuance_notes: roteiro direto de fala para o apresentador (2 a 4 frases, tom analítico, apontando a sutileza retórica e o gancho).\n"
        "- summary2: segundo parágrafo enxuto e incisivo para aparecer no palco expondo a contradição ou recorte.\n"
        "- deep: explicação mais densa para a gaveta expansível [Espaço] ancorada apenas nos dados acima (sem inventar números)."
    )
    try:
        result, _meta = llm_client.generate_structured(
            prompt=prompt,
            pydantic_model=NuanceSuggestLLMOutput,
            json_schema=NUANCE_JSON_SCHEMA,
            schema_name="nuance_suggestion",
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Servidor LLM local indisponível ou falhou ao gerar nuance: {exc}",
        ) from exc


@router.get("", response_model=List[DeckSummaryOut])
def list_decks(
    modo: Optional[str] = Query(default=None, description="Filtrar por 'ensaio' ou 'live'"),
    db: Session = Depends(get_db),
) -> List[DeckSummaryOut]:
    """Lista ensaios e pautas de live salvos (cria um ensaio inicial se vazio)."""
    ensure_default_deck(db)
    query = db.query(PresentationDeck)
    if modo:
        query = query.filter(PresentationDeck.modo == modo)
    decks = query.order_by(PresentationDeck.atualizado_em.desc()).all()
    return [_to_summary(d) for d in decks]


@router.post("", response_model=DeckOut, status_code=status.HTTP_201_CREATED)
def create_deck(payload: DeckCreateUpdate, db: Session = Depends(get_db)) -> DeckOut:
    """Cria um novo roteiro de ensaio ou pauta ao vivo."""
    deck = _persist_deck(db, payload, is_demo=False)
    return DeckOut.model_validate(deck)


@router.post("/from-event/{event_id}", response_model=DeckOut, status_code=status.HTTP_201_CREATED)
def create_deck_from_event(event_id: str, db: Session = Depends(get_db)) -> DeckOut:
    """Gera automaticamente um roteiro de Ensaio com Nuances a partir de um Evento/Dossiê."""
    ensure_demo_seed(db)
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evento '{event_id}' não encontrado.")
    payload = _build_essay_payload_from_event(db, event)
    deck = _persist_deck(db, payload, is_demo=event.is_demo)
    return DeckOut.model_validate(deck)


@router.post("/from-live-feed", response_model=DeckOut, status_code=status.HTTP_201_CREATED)
def create_deck_from_live_feed(
    limit: int = Query(default=10, ge=1, le=10),
    theme: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> DeckOut:
    """Monta uma pauta de Giro Ao Vivo com até 10 acontecimentos recentes e ticker RSS."""
    payload = _build_live_payload_from_feed(db, limit=limit, theme=theme)
    is_all_demo = db.query(Event).filter(Event.is_demo.is_(False)).count() == 0
    deck = _persist_deck(db, payload, is_demo=is_all_demo)
    return DeckOut.model_validate(deck)


@router.post("/collect-now")
def trigger_collect_now() -> Dict[str, Any]:
    """Dispara coleta RSS imediata e reagrupamento usando o ciclo thread-safe compartilhado."""
    return run_collection_and_clustering_cycle()


@router.get("/{deck_id}", response_model=DeckOut)
def get_deck(deck_id: str, db: Session = Depends(get_db)) -> DeckOut:
    """Retorna um ensaio ou pauta ao vivo completo."""
    ensure_default_deck(db)
    deck = db.query(PresentationDeck).filter(PresentationDeck.id == deck_id).first()
    if deck is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deck '{deck_id}' não encontrado.")
    return DeckOut.model_validate(deck)


@router.put("/{deck_id}", response_model=DeckOut)
def update_deck(deck_id: str, payload: DeckCreateUpdate, db: Session = Depends(get_db)) -> DeckOut:
    """Salva edições de slides, nuances, KPIs, gráficos e ticker feitas no Modo Estúdio."""
    deck = db.query(PresentationDeck).filter(PresentationDeck.id == deck_id).first()
    if deck is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deck '{deck_id}' não encontrado.")
    deck.titulo = payload.titulo.strip() or "Roteiro sem título"
    deck.modo = payload.modo
    deck.event_id = _resolve_valid_event_id(db, payload.event_id)
    deck.kpis = [k.model_dump() for k in payload.kpis]
    deck.slides = [s.model_dump() for s in payload.slides]
    deck.charts = [c.model_dump() for c in payload.charts]
    deck.ticker_items = list(payload.ticker_items)
    deck.is_demo = False
    deck.atualizado_em = utcnow()
    db.commit()
    db.refresh(deck)
    return DeckOut.model_validate(deck)


@router.delete("/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deck(deck_id: str, db: Session = Depends(get_db)) -> Response:
    """Remove um ensaio ou pauta salva."""
    deck = db.query(PresentationDeck).filter(PresentationDeck.id == deck_id).first()
    if deck is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deck '{deck_id}' não encontrado.")
    db.delete(deck)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{deck_id}/export-html")
def export_deck_standalone_html(deck_id: str, db: Session = Depends(get_db)) -> Response:
    """Exporta o ensaio/pauta como arquivo HTML autônomo (estilo exemplo.html) para uso offline."""
    deck = db.query(PresentationDeck).filter(PresentationDeck.id == deck_id).first()
    if deck is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Deck '{deck_id}' não encontrado.")

    safe_json = json.dumps(
        DeckOut.model_validate(deck).model_dump(mode="json"),
        ensure_ascii=False,
    ).replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_lib.escape(deck.titulo)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
:root {{ --bg:#050505; --surface:#0b0b0d; --surface-2:#121216; --ink:#e8e8e3; --ink-dim:#8a8a84; --line:#242422; --line-bright:#4a4a46; --crimson:#ff2a2a; --amber:#ff9900; --cyan:#00e5ff; --lime:#a6ff00; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:var(--bg); color:var(--ink); font-family:'JetBrains Mono',monospace; height:100vh; width:100vw; overflow:hidden; display:grid; grid-template-rows:54px 92px 1fr 50px; user-select:none; }}
.top-bar {{ border-bottom:1px solid var(--line); background:#000; display:flex; justify-content:space-between; align-items:center; padding:0 28px; gap:16px; }}
.top-kpis {{ display:flex; gap:22px; font-size:11.5px; flex-wrap:wrap; }}
.kpi-pill span {{ color:var(--ink-dim); margin-right:5px; }}
.action-btn {{ background:var(--surface); color:var(--ink); border:1px solid var(--line-bright); padding:6px 12px; font-family:inherit; font-size:11px; cursor:pointer; }}
.action-btn.active,.action-btn:hover {{ background:var(--ink); color:#000; font-weight:700; }}
.timeline-nav {{ border-bottom:1px solid var(--line); background:var(--surface); padding:0 28px; display:flex; align-items:center; position:relative; }}
.track-line {{ position:absolute; left:52px; right:52px; top:42%; height:2px; background:var(--line-bright); z-index:1; }}
.track-progress {{ position:absolute; left:52px; top:42%; height:2px; background:var(--amber); z-index:2; transition:width .3s ease; }}
.nodes-wrapper {{ display:flex; justify-content:space-between; width:100%; position:relative; z-index:3; }}
.nav-node {{ display:flex; flex-direction:column; align-items:center; cursor:pointer; flex:1; }}
.node-dot {{ width:15px; height:15px; background:#000; border:2px solid var(--line-bright); margin-bottom:9px; }}
.nav-node.active .node-dot {{ width:19px; height:19px; background:var(--ink); border-color:#fff; box-shadow:0 0 14px rgba(255,255,255,.45); }}
.nav-node.past .node-dot {{ background:var(--amber); border-color:var(--amber); }}
.node-date {{ font-size:10px; color:var(--ink-dim); font-weight:600; text-align:center; white-space:nowrap; }}
.nav-node.active .node-date {{ color:#fff; font-weight:700; }}
.stage {{ display:grid; grid-template-columns:1fr 430px; height:100%; overflow:hidden; }}
.slide-main {{ padding:34px 46px; border-right:1px solid var(--line); display:flex; flex-direction:column; justify-content:space-between; overflow-y:auto; }}
.slide-counter {{ font-size:12px; font-weight:700; padding:3px 10px; border:1px solid var(--line-bright); background:#000; margin-right:12px; }}
.slide-timestamp {{ font-size:12.5px; color:var(--amber); font-weight:600; }}
.slide-headline {{ font-family:'Instrument Serif',Georgia,serif; font-size:clamp(2.1rem,3.2vw,3.1rem); line-height:1.06; color:#fff; font-weight:400; margin:16px 0; max-width:34ch; }}
.slide-summary {{ font-size:14.5px; line-height:1.65; color:#d6d6d0; max-width:78ch; margin-bottom:14px; }}
.slide-summary-2 {{ font-size:13.5px; line-height:1.6; color:#a8a8a2; max-width:78ch; margin-bottom:18px; }}
.nuance-box {{ display:none; margin-bottom:16px; padding:12px 16px; background:#141109; border-left:3px solid var(--lime); font-size:12px; line-height:1.55; color:#d9f99d; }}
.nuance-box.open {{ display:block; }}
.expand-trigger {{ background:var(--surface-2); color:#fff; border:1px solid var(--line-bright); padding:10px 16px; font-family:inherit; font-size:12px; cursor:pointer; }}
.expand-drawer {{ display:none; margin-top:12px; background:#09090b; border:1px solid var(--line-bright); border-left:3px solid var(--amber); padding:16px 20px; }}
.expand-drawer.open {{ display:block; }}
.drawer-text {{ font-size:13px; line-height:1.6; color:#c4c4be; margin-bottom:10px; }}
.drawer-code {{ background:#000; border:1px solid var(--line); padding:8px 12px; font-size:11.5px; color:var(--cyan); }}
.slide-sidebar {{ background:var(--surface); padding:28px; display:flex; flex-direction:column; justify-content:space-between; overflow-y:auto; }}
.sidebar-metric-box {{ border:1px solid var(--line-bright); background:#000; padding:18px 20px; margin-bottom:18px; }}
.sidebar-metric-label {{ font-size:10.5px; color:var(--ink-dim); display:block; margin-bottom:6px; }}
.sidebar-metric-val {{ font-family:'Instrument Serif',serif; font-size:3rem; line-height:1; color:#fff; margin-bottom:8px; }}
.sidebar-metric-sub {{ font-size:11.5px; color:var(--ink-dim); line-height:1.4; }}
.sidebar-details-list {{ list-style:none; border-top:1px solid var(--line); margin-bottom:18px; }}
.sidebar-details-list li {{ display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px dotted var(--line); font-size:11.5px; gap:10px; }}
.sidebar-details-list li span:first-child {{ color:var(--ink-dim); }}
.src-btn {{ display:flex; justify-content:space-between; text-decoration:none; color:var(--ink); background:var(--bg); border:1px solid var(--line-bright); padding:8px 12px; font-size:11px; margin-bottom:6px; }}
.webcam-frame {{ display:none; height:180px; border:1px dashed var(--line-bright); background:rgba(0,0,0,.65); align-items:center; justify-content:center; color:var(--ink-dim); font-size:11px; margin-top:14px; }}
.webcam-frame.visible {{ display:flex; }}
.charts-modal {{ position:fixed; top:54px; left:0; right:0; bottom:50px; background:rgba(5,5,5,.97); z-index:50; display:none; grid-template-columns:repeat(3,1fr); gap:22px; padding:32px; overflow-y:auto; }}
.charts-modal.open {{ display:grid; }}
.modal-card {{ background:var(--surface); border:1px solid var(--line-bright); padding:24px; }}
.modal-card h3 {{ font-family:'Instrument Serif',serif; font-size:1.8rem; font-weight:400; margin-bottom:6px; color:#fff; }}
.modal-card p {{ color:var(--ink-dim); font-size:11.5px; margin-bottom:18px; line-height:1.45; }}
.scale-row {{ display:grid; grid-template-columns:130px 1fr 70px; align-items:center; gap:10px; margin-bottom:12px; font-size:11.5px; }}
.scale-bar-wrap {{ height:16px; background:#000; border:1px solid var(--line); }}
.scale-bar {{ height:100%; background:var(--amber); }}
.scale-bar.crimson {{ background:var(--crimson); }}
.scale-bar.cyan {{ background:var(--cyan); }}
.scale-bar.dim {{ background:var(--line-bright); }}
.bottom-deck {{ border-top:1px solid var(--line); background:#000; padding:0 28px; display:flex; justify-content:space-between; align-items:center; font-size:11.5px; overflow:hidden; }}
.kbd {{ background:var(--surface-2); border:1px solid var(--line-bright); color:#fff; padding:2px 6px; font-size:10px; }}
.nav-arrow {{ background:var(--surface); color:#fff; border:1px solid var(--line-bright); padding:6px 14px; font-family:inherit; font-size:11.5px; cursor:pointer; }}
.ticker {{ white-space:nowrap; overflow:hidden; width:100%; color:#fff; }}
</style>
</head>
<body>
<header class="top-bar"><div class="top-kpis" id="kpis"></div><div>
<button class="action-btn" onclick="toggleNuance()">[ N ] Notas</button>
<button class="action-btn" onclick="toggleTicker()">[ T ] Ticker</button>
<button class="action-btn" onclick="toggleCharts()">[ G ] Gráficos</button>
<button class="action-btn" onclick="toggleCam()">[ C ] Webcam</button>
</div></header>
<nav class="timeline-nav"><div class="track-line"></div><div class="track-progress" id="prog"></div><div class="nodes-wrapper" id="nodes"></div></nav>
<main class="stage"><section class="slide-main"><div><div><span class="slide-counter" id="cnt"></span><span class="slide-timestamp" id="ts"></span></div>
<h1 class="slide-headline" id="ttl"></h1><p class="slide-summary" id="sum1"></p><p class="slide-summary-2" id="sum2"></p>
<div class="nuance-box" id="nuance"></div></div>
<div><button class="expand-trigger" onclick="toggleDrawer()">[ Espaço ] Expandir Detalhes & Evidências</button>
<div class="expand-drawer" id="drawer"><p class="drawer-text" id="deep"></p><div class="drawer-code" id="code"></div></div></div></section>
<aside class="slide-sidebar"><div><div class="sidebar-metric-box"><span class="sidebar-metric-label" id="mlbl"></span><div class="sidebar-metric-val" id="mval"></div><div class="sidebar-metric-sub" id="msub"></div></div>
<ul class="sidebar-details-list" id="specs"></ul><div id="links"></div></div><div class="webcam-frame" id="cam">[ ÁREA RESERVADA PARA CÂMERA / OBS (16:9) ]</div></aside></main>
<section class="charts-modal" id="charts"></section>
<footer class="bottom-deck" id="footer"></footer>
<script>
const DECK = {safe_json};
let idx = 0, showTicker = false;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));
const safeUrl = (u) => /^https?:\\/\\//i.test(String(u||'')) ? esc(u) : '';
document.getElementById('kpis').innerHTML = (DECK.kpis||[]).map(k => `<div class="kpi-pill"><span>${{esc(k.label)}}</span><strong style="color:${{esc(k.color)}}">${{esc(k.value)}}</strong></div>`).join('');
document.getElementById('nodes').innerHTML = (DECK.slides||[]).map((s,i) => `<div class="nav-node" onclick="go(${{i}})"><div class="node-dot"></div><span class="node-date">${{esc(s.shortDate)}}</span></div>`).join('');
document.getElementById('charts').innerHTML = (DECK.charts||[]).map(c => `<div class="modal-card"><h3>${{esc(c.title)}}</h3><p>${{esc(c.subtitle)}}</p>${{(c.rows||[]).map(r => `<div class="scale-row"><span>${{esc(r.label)}}</span><div class="scale-bar-wrap"><div class="scale-bar ${{['crimson','cyan','dim'].includes(r.color)?r.color:''}}" style="width:${{Number(r.pct)||0}}%"></div></div><span style="text-align:right">${{esc(r.displayValue)}}</span></div>`).join('')}}</div>`).join('');
function renderFooter() {{
  const f = document.getElementById('footer');
  if (showTicker && (DECK.ticker_items||[]).length) {{
    f.innerHTML = `<div class="ticker"><strong style="color:var(--crimson);margin-right:12px;">● GIRO:</strong>${{esc(DECK.ticker_items.join('  ///  '))}}</div>`;
  }} else {{
    f.innerHTML = `<div><span class="kbd">←</span> <span class="kbd">→</span> Navegar &nbsp; <span class="kbd">Espaço</span> Detalhes &nbsp; <span class="kbd">N</span> Nuances &nbsp; <span class="kbd">T</span> Ticker &nbsp; <span class="kbd">G</span> Gráficos &nbsp; <span class="kbd">C</span> Câmera</div><div><button class="nav-arrow" onclick="go(idx-1)">← Anterior</button> <button class="nav-arrow" onclick="go(idx+1)">Próximo →</button></div>`;
  }}
}}
function go(n) {{
  if (!DECK.slides.length || n < 0 || n >= DECK.slides.length) return;
  idx = n; const s = DECK.slides[idx];
  document.getElementById('cnt').textContent = `${{String(idx+1).padStart(2,'0')}} / ${{String(DECK.slides.length).padStart(2,'0')}}`;
  document.getElementById('ts').textContent = s.timestamp || '';
  document.getElementById('ttl').textContent = s.title || '';
  document.getElementById('sum1').textContent = s.summary || '';
  document.getElementById('sum2').textContent = s.summary2 || '';
  document.getElementById('nuance').textContent = s.nuance_notes ? `Roteiro / Nuance: ${{s.nuance_notes}}` : 'Sem notas de nuance neste slide.';
  document.getElementById('deep').textContent = s.deep || '';
  document.getElementById('code').textContent = s.code || '';
  document.getElementById('mlbl').textContent = s.metricLabel || '';
  const mv = document.getElementById('mval'); mv.textContent = s.metricVal || ''; mv.style.color = s.metricColor || '#fff';
  document.getElementById('msub').textContent = s.metricSub || '';
  document.getElementById('specs').innerHTML = (s.specs||[]).map(p => `<li><span>${{esc(p[0])}}</span><span>${{esc(p[1])}}</span></li>`).join('');
  document.getElementById('links').innerHTML = (s.links||[]).filter(l => safeUrl(l.url)).map(l => `<a class="src-btn" href="${{safeUrl(l.url)}}" target="_blank" rel="noopener"><span>${{esc(l.label)}}</span><span>↗</span></a>`).join('');
  document.getElementById('prog').style.width = DECK.slides.length > 1 ? `${{(idx/(DECK.slides.length-1))*91}}%` : '0%';
  document.querySelectorAll('.nav-node').forEach((el,i) => {{ el.classList.toggle('active', i===idx); el.classList.toggle('past', i<idx); }});
}}
function toggleDrawer() {{ document.getElementById('drawer').classList.toggle('open'); }}
function toggleCharts() {{ document.getElementById('charts').classList.toggle('open'); }}
function toggleCam() {{ document.getElementById('cam').classList.toggle('visible'); }}
function toggleNuance() {{ document.getElementById('nuance').classList.toggle('open'); }}
function toggleTicker() {{ showTicker = !showTicker; renderFooter(); }}
document.addEventListener('keydown', e => {{
  if (e.key==='ArrowRight') go(idx+1);
  else if (e.key==='ArrowLeft') go(idx-1);
  else if (e.key===' ' || e.key.toLowerCase()==='e') {{ e.preventDefault(); toggleDrawer(); }}
  else if (e.key.toLowerCase()==='g') toggleCharts();
  else if (e.key.toLowerCase()==='c') toggleCam();
  else if (e.key.toLowerCase()==='n') toggleNuance();
  else if (e.key.toLowerCase()==='t') toggleTicker();
}});
renderFooter();
go(0);
</script>
</body>
</html>"""

    filename = f"ensaio-{deck.id[:8]}.html"
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
