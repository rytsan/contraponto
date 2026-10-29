import json
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models import Article, Event, EventAnalysis, Source
from app.schemas import (
    CoordinatesSchema,
    CoveragePairSchema,
    DataVisualizationSchema,
    DossierAuditMetadata,
    DossierMetadataArticleItem,
    DossierSchema,
    EventConsolidationLLMOutput,
)
from app.analysis.evidence_verifier import recalculate_dossier_confidence
from app.analysis.llm_client import (
    LLMCallMetadata,
    LlamaCppClient,
    load_json_schema,
    load_prompt_template,
    validate_against_json_schema,
)


def _build_consolidation_json_schema(full_event_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai o sub-schema Draft 2020-12 da Etapa 3.2 a partir de event_analysis.json."""
    defs = full_event_schema.get("$defs", {})
    consolidation_def = defs.get("llm_consolidation", {})
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "EventConsolidationLLMOutput",
        **consolidation_def,
        "$defs": {k: v for k, v in defs.items() if k != "llm_consolidation"},
    }


def _filter_valid_visualizations(
    visualizations: List[DataVisualizationSchema],
    valid_article_ids: set,
) -> List[DataVisualizationSchema]:
    """
    Garante que gráficos só existam quando todos os source_article_ids pertencerem
    às matérias reais do evento e labels/values possuírem tamanhos compatíveis e não vazios.
    """
    filtered: List[DataVisualizationSchema] = []
    for viz in visualizations:
        if not viz.labels or not viz.values:
            continue
        if len(viz.labels) != len(viz.values):
            continue
        if not viz.source_article_ids:
            continue
        if not all(aid in valid_article_ids for aid in viz.source_article_ids):
            continue
        filtered.append(viz)
    return filtered


def build_articles_audit_registry(
    db: Optional[Session],
    articles: List[Article],
) -> List[DossierMetadataArticleItem]:
    """Constrói o registro completo de auditoria das fontes para a Cena 6."""
    sources_map: Dict[str, Source] = {}
    if db is not None and articles:
        src_ids = list({a.source_id for a in articles})
        for s in db.query(Source).filter(Source.id.in_(src_ids)).all():
            sources_map[s.id] = s

    registry: List[DossierMetadataArticleItem] = []
    for art in articles:
        src = sources_map.get(art.source_id)
        meta = art.metadados or {}
        pos = (
            src.posicao_editorial_declarada
            if src
            else str(meta.get("posicao_editorial_declarada", "Não informada"))
        )
        cat = (
            src.categoria_editorial
            if src
            else str(meta.get("categoria_editorial", ""))
        )
        registry.append(
            DossierMetadataArticleItem(
                id=art.id,
                source_id=art.source_id,
                veiculo=art.veiculo,
                autor=art.autor,
                data_publicacao=art.data_publicacao,
                data_coleta=art.data_coleta,
                url_canonica=art.url_canonica,
                titulo=art.titulo,
                posicao_editorial_declarada=pos,
                categoria_editorial=cat,
                metodo_coleta=art.metodo_coleta,
                is_demo=art.is_demo,
            )
        )
    return registry


def consolidate_event_marxist_analysis(
    event: Event,
    articles: List[Article],
    coverage_pairs: List[CoveragePairSchema],
    llm_client: LlamaCppClient,
    db: Optional[Session] = None,
    prior_execution_ms: int = 0,
) -> Tuple[DossierSchema, LLMCallMetadata]:
    """
    Executa a Etapa 3.2 (Consolidação Marxista-Leninista do Evento) e aplica
    as regras de integridade da Etapa 3.3 (recálculo programático de `confidence`
    e validação estrutural contra `event_analysis.json`).
    """
    full_event_schema = load_json_schema("event_analysis.json")
    consolidation_schema = _build_consolidation_json_schema(full_event_schema)
    prompt_template = load_prompt_template("marxist_analyzer.txt")

    compact_biases = [pair.model_dump(mode="json") for pair in coverage_pairs]
    compact_biases_json = json.dumps(compact_biases, ensure_ascii=False, indent=2)

    base_chars = len(prompt_template) + len(compact_biases_json) + 500
    remaining_budget = llm_client.compute_text_budget_chars(
        system_and_template_chars=base_chars,
        reserved_output_tokens=2000,
    )

    if remaining_budget >= 600 and articles:
        per_article_chars = max(200, remaining_budget // len(articles))
        excerpts = [
            f"[{a.id} | {a.veiculo}]: {(a.texto_limpo or a.resumo)[:per_article_chars]}"
            for a in articles
        ]
        original_texts_excerpt = "\n\n".join(excerpts)
    else:
        original_texts_excerpt = "(Omitido por orçamento de contexto; utilize os dados compactados acima.)"

    prompt = prompt_template.format(
        event_id=event.id,
        theme=event.tema,
        location=event.local or "Não especificado",
        compact_bias_analyses_json=compact_biases_json,
        original_texts_excerpt=original_texts_excerpt,
    )

    llm_output, meta = llm_client.generate_structured(
        prompt=prompt,
        pydantic_model=EventConsolidationLLMOutput,
        json_schema=consolidation_schema,
        schema_name="event_consolidation",
        root_schema=full_event_schema,
    )

    valid_article_ids = {a.id for a in articles} | {p.article_id for p in coverage_pairs}
    valid_visualizations = _filter_valid_visualizations(
        llm_output.data_visualizations,
        valid_article_ids=valid_article_ids,
    )

    # Regra 3.3.4: O campo confidence final é recalculado pelo sistema; o valor do LLM é descartado.
    recalculated_confidence = recalculate_dossier_confidence(coverage_pairs)

    total_time_ms = prior_execution_ms + meta.execution_time_ms
    audit_meta = DossierAuditMetadata(
        analyzed_at=meta.executed_at,
        llm_model=meta.model_name,
        num_ctx=meta.num_ctx,
        execution_time_ms=total_time_ms,
        is_demo=event.is_demo,
        articles_registry=build_articles_audit_registry(db, articles),
    )

    dossier = DossierSchema(
        event_id=event.id,
        title=event.titulo_provisorio,
        is_demo=event.is_demo,
        factual_anchor=llm_output.factual_anchor,
        theme=event.tema,
        location=event.local,
        coordinates=CoordinatesSchema(lat=event.lat, lon=event.lon),
        coverage_pairs=coverage_pairs,
        actors=llm_output.actors,
        marxist_leninist_analysis=llm_output.marxist_leninist_analysis,
        reader_questions=llm_output.reader_questions,
        data_visualizations=valid_visualizations,
        confidence=recalculated_confidence,
        audit_metadata=audit_meta,
    )

    dossier_dict = dossier.model_dump(mode="json")
    validate_against_json_schema(dossier_dict, full_event_schema)

    if db is not None:
        existing = (
            db.query(EventAnalysis)
            .filter(EventAnalysis.event_id == event.id)
            .first()
        )
        if existing is None:
            existing = EventAnalysis(
                event_id=event.id,
                dossier_payload=dossier_dict,
                confidence=recalculated_confidence,
                modelo_llm=meta.model_name,
                num_ctx=meta.num_ctx,
                tempo_execucao_ms=total_time_ms,
                criado_em=meta.executed_at,
                atualizado_em=meta.executed_at,
            )
            db.add(existing)
        else:
            existing.dossier_payload = dossier_dict
            existing.confidence = recalculated_confidence
            existing.modelo_llm = meta.model_name
            existing.num_ctx = meta.num_ctx
            existing.tempo_execucao_ms = total_time_ms
            existing.atualizado_em = meta.executed_at
            db.add(existing)
        db.commit()

    return dossier, meta
