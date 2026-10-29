import json
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models import Article, ArticleBiasAnalysis, Source
from app.schemas import BiasAnalysisLLMOutput, CoveragePairSchema, EvidenceQuoteSchema
from app.analysis.evidence_verifier import verify_article_quotes
from app.analysis.llm_client import (
    LLMCallMetadata,
    LlamaCppClient,
    load_json_schema,
    load_prompt_template,
)


def _resolve_source_position(db: Optional[Session], article: Article) -> str:
    """Obtém a posição editorial declarada da fonte do artigo."""
    if db is not None:
        src = db.query(Source).filter(Source.id == article.source_id).first()
        if src and src.posicao_editorial_declarada:
            return src.posicao_editorial_declarada
    meta = article.metadados or {}
    if meta.get("posicao_editorial_declarada"):
        return str(meta["posicao_editorial_declarada"])
    return "Posição editorial não informada"


def analyze_article_bias(
    article: Article,
    llm_client: LlamaCppClient,
    db: Optional[Session] = None,
    max_attempts: int = 3,
) -> Tuple[CoveragePairSchema, LLMCallMetadata, float]:
    """
    Executa a Etapa 3.1 (Análise de viés por matéria) seguida da Etapa 3.3 (Verificação fuzzy).
    Se mais de 30% dos trechos de uma matéria ficarem `verified: false`, reprocessa
    a análise dessa matéria (contabilizado no limite de 3 tentativas).
    """
    bias_schema = load_json_schema("bias_analysis.json")
    prompt_template = load_prompt_template("bias_analyzer.txt")
    source_position = _resolve_source_position(db, article)

    budget_chars = llm_client.compute_text_budget_chars(
        system_and_template_chars=len(prompt_template) + 600,
        reserved_output_tokens=1500,
    )
    full_reference_text = f"{article.titulo}\n{article.resumo}\n{article.texto_limpo}".strip()
    truncated_article_text = (article.texto_limpo or article.resumo or article.titulo)[:budget_chars]

    base_prompt = prompt_template.format(
        article_id=article.id,
        source=article.veiculo,
        source_position=source_position,
        url=article.url_canonica,
        headline=article.titulo,
        article_text=truncated_article_text,
    )

    attempts_cap = max(1, min(3, max_attempts))
    total_attempts_used = 0
    total_exec_ms = 0
    last_meta: Optional[LLMCallMetadata] = None
    last_llm_output: Optional[BiasAnalysisLLMOutput] = None
    verified_quotes: List[EvidenceQuoteSchema] = []
    verified_ratio = 0.0
    already_verified_raw: List[dict] = []

    current_prompt = base_prompt

    while total_attempts_used < attempts_cap:
        remaining_for_client = max(1, attempts_cap - total_attempts_used)
        llm_client.max_retries = remaining_for_client

        llm_output, meta = llm_client.generate_structured(
            prompt=current_prompt,
            pydantic_model=BiasAnalysisLLMOutput,
            json_schema=bias_schema,
            schema_name="bias_analysis",
            preserved_evidence_quotes=already_verified_raw or None,
        )
        total_attempts_used += meta.attempts
        total_exec_ms += meta.execution_time_ms
        last_meta = meta
        last_llm_output = llm_output

        verified_quotes, verified_ratio, needs_reprocess = verify_article_quotes(
            quotes=llm_output.evidence_quotes,
            source_text=full_reference_text,
        )

        already_verified_raw = [
            {"quote": q.quote, "context": q.context}
            for q in verified_quotes
            if q.verified
        ]

        if not needs_reprocess or total_attempts_used >= attempts_cap:
            break

        unverified_strs = [q.quote for q in verified_quotes if not q.verified]
        current_prompt = (
            f"{base_prompt}\n\n"
            "ATENÇÃO — REPROCESSAMENTO OBRIGATÓRIO POR FALHA DE VERIFICAÇÃO TEXTUAL (ETAPA 3.3):\n"
            f"Mais de 30% das citações anteriores não foram localizadas literalmente no texto original: {json.dumps(unverified_strs, ensure_ascii=False)}.\n"
            "Substitua os trechos não verificados por substrings LITERAIS E IDÊNTICAS extraídas do TEXTO ORIGINAL DA MATÉRIA acima."
        )

    assert last_llm_output is not None and last_meta is not None

    final_meta = LLMCallMetadata(
        executed_at=last_meta.executed_at,
        model_name=last_meta.model_name,
        num_ctx=last_meta.num_ctx,
        execution_time_ms=total_exec_ms,
        used_fallback_json_object=last_meta.used_fallback_json_object,
        attempts=total_attempts_used,
    )

    coverage_pair = CoveragePairSchema(
        article_id=article.id,
        source=article.veiculo,
        source_position=source_position,
        url=article.url_canonica,
        headline=article.titulo,
        central_thesis=last_llm_output.central_thesis,
        valued_actors=last_llm_output.valued_actors,
        devalued_actors=last_llm_output.devalued_actors,
        ideological_vocabulary=last_llm_output.ideological_vocabulary,
        privileged_sources=last_llm_output.privileged_sources,
        likely_omissions=last_llm_output.likely_omissions,
        state_framing=last_llm_output.state_framing,
        market_framing=last_llm_output.market_framing,
        labor_framing=last_llm_output.labor_framing,
        protest_framing=last_llm_output.protest_framing,
        political_effect=last_llm_output.political_effect,
        evidence_quotes=verified_quotes,
    )

    if db is not None:
        record = (
            db.query(ArticleBiasAnalysis)
            .filter(
                ArticleBiasAnalysis.article_id == article.id,
                ArticleBiasAnalysis.event_id == article.event_id,
            )
            .first()
        )
        if record is None:
            record = ArticleBiasAnalysis(
                article_id=article.id,
                event_id=article.event_id,
                payload=coverage_pair.model_dump(mode="json"),
                verified_ratio=verified_ratio,
                modelo_llm=final_meta.model_name,
                num_ctx=final_meta.num_ctx,
                tempo_execucao_ms=final_meta.execution_time_ms,
                criado_em=final_meta.executed_at,
            )
            db.add(record)
        else:
            record.payload = coverage_pair.model_dump(mode="json")
            record.verified_ratio = verified_ratio
            record.modelo_llm = final_meta.model_name
            record.num_ctx = final_meta.num_ctx
            record.tempo_execucao_ms = final_meta.execution_time_ms
            record.criado_em = final_meta.executed_at
            db.add(record)
        db.commit()

    return coverage_pair, final_meta, verified_ratio
