import json
from datetime import datetime, timezone
from typing import Any, Dict, List
import httpx
from sqlalchemy.orm import Session
from app.models import Article, Event, Source
from app.schemas import EvidenceQuoteLLM
from app.analysis.bias_analyzer import analyze_article_bias
from app.analysis.evidence_verifier import (
    recalculate_dossier_confidence,
    verify_article_quotes,
    verify_single_quote,
)
from app.analysis.llm_client import LlamaCppClient
from app.analysis.analysis_jobs import create_or_resume_analysis_job, execute_analysis_job


SAMPLE_SOURCE_TEXT = (
    "A paralisação decretada pelo Sindicato dos Metroviários e motoristas em São Paulo "
    "provocou filas e atrasos severos no deslocamento matinal desta quarta-feira. "
    "Segundo estimativas preliminares de federações empresariais como a FIESP, "
    "o setor de comércio e serviços pode registrar perdas superiores a R$ 120 milhões "
    "caso o movimento paredista se estenda pelos próximos dias."
)


def test_verify_single_quote_true_for_real_and_false_for_invented() -> None:
    real_quote = "o setor de comércio e serviços pode registrar perdas superiores a R$ 120 milhões"
    is_verified, score = verify_single_quote(real_quote, SAMPLE_SOURCE_TEXT)
    assert is_verified is True
    assert score >= 92.0

    invented_quote = "o sindicato confessou que a greve tinha objetivo puramente eleitoral e partidário"
    is_verified_inv, score_inv = verify_single_quote(invented_quote, SAMPLE_SOURCE_TEXT)
    assert is_verified_inv is False
    assert score_inv < 92.0


def test_verify_article_quotes_triggers_reprocess_when_over_30_percent_fail() -> None:
    quotes = [
        EvidenceQuoteLLM(
            quote="A paralisação decretada pelo Sindicato dos Metroviários e motoristas em São Paulo",
            context="Trecho real 1",
        ),
        EvidenceQuoteLLM(
            quote="Trecho completamente inventado pelo modelo que não consta na matéria original",
            context="Alucinação 1",
        ),
    ]
    verified_list, ratio, needs_reprocess = verify_article_quotes(quotes, SAMPLE_SOURCE_TEXT)
    assert len(verified_list) == 2
    assert verified_list[0].verified is True
    assert verified_list[1].verified is False
    assert ratio == 0.5
    # 50% falhou (> 30%), logo precisa reprocessar
    assert needs_reprocess is True


def test_bias_analyzer_reprocesses_when_over_30_percent_quotes_unverified(
    db_session: Session,
) -> None:
    source = Source(
        id="src_reprocess",
        nome="Diário Demo",
        url_rss="https://demo.local/rss",
        categoria_editorial="grande_midia_liberal",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Liberal fictícia",
        descricao="Fonte de teste",
        is_demo=True,
    )
    article = Article(
        id="art-reprocess-1",
        source_id=source.id,
        titulo="Paralisação no transporte de São Paulo",
        url_canonica="https://demo.local/greve-1",
        guid="g-rep-1",
        veiculo=source.nome,
        data_publicacao=datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc),
        data_coleta=datetime(2026, 10, 28, 10, 5, tzinfo=timezone.utc),
        texto_limpo=SAMPLE_SOURCE_TEXT,
        resumo="Resumo da paralisação em São Paulo.",
        idioma="pt",
        hash_conteudo="hash-rep-1",
        metodo_coleta="rss_full",
        metadados={},
        is_demo=True,
    )
    db_session.add_all([source, article])
    db_session.commit()

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        if str(request.url).endswith("/props"):
            return httpx.Response(200, json={"model_alias": "Meta-Llama-3.1-8B-Instruct-Q4_K_M"})
        call_count += 1
        if call_count == 1:
            # 1ª resposta tem 1 citação verdadeira e 1 inventada (50% falha -> força reprocesso)
            bad_quotes = [
                {
                    "quote": "A paralisação decretada pelo Sindicato dos Metroviários e motoristas em São Paulo",
                    "context": "Abertura",
                },
                {
                    "quote": "Citação inventada que jamais existiu no texto da reportagem original",
                    "context": "Inventada",
                },
            ]
            payload = {
                "central_thesis": "Enquadramento focado no impacto comercial.",
                "valued_actors": ["FIESP"],
                "devalued_actors": ["Sindicato dos Metroviários"],
                "ideological_vocabulary": ["atrasos severos"],
                "privileged_sources": ["FIESP"],
                "likely_omissions": ["Reivindicações salariais"],
                "state_framing": "sem_evidencia_suficiente",
                "market_framing": "Comércio destacado como vítima.",
                "labor_framing": "Trabalhadores responsabilizados pelos atrasos.",
                "protest_framing": "Greve vista pelo prisma do prejuízo econômico.",
                "political_effect": "Pressão pública contra a paralisação.",
                "evidence_quotes": bad_quotes,
            }
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})

        # 2ª resposta (reprocessamento) traz ambas as citações literais do texto
        good_quotes = [
            {
                "quote": "A paralisação decretada pelo Sindicato dos Metroviários e motoristas em São Paulo",
                "context": "Abertura",
            },
            {
                "quote": "o setor de comércio e serviços pode registrar perdas superiores a R$ 120 milhões",
                "context": "Estimativa da FIESP",
            },
        ]
        payload_ok = {
            "central_thesis": "Enquadramento focado no impacto comercial.",
            "valued_actors": ["FIESP"],
            "devalued_actors": ["Sindicato dos Metroviários"],
            "ideological_vocabulary": ["atrasos severos"],
            "privileged_sources": ["FIESP"],
            "likely_omissions": ["Reivindicações salariais"],
            "state_framing": "sem_evidencia_suficiente",
            "market_framing": "Comércio destacado como vítima.",
            "labor_framing": "Trabalhadores responsabilizados pelos atrasos.",
            "protest_framing": "Greve vista pelo prisma do prejuízo econômico.",
            "political_effect": "Pressão pública contra a paralisação.",
            "evidence_quotes": good_quotes,
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload_ok)}}]})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as mock_http:
        llm_client = LlamaCppClient(http_client=mock_http)
        pair, meta, verified_ratio = analyze_article_bias(
            article=article,
            llm_client=llm_client,
            db=db_session,
            max_attempts=3,
        )

    assert call_count == 2
    assert meta.attempts == 2
    assert verified_ratio == 1.0
    assert all(q.verified for q in pair.evidence_quotes)


def test_confidence_recalculated_by_system_and_resumable_analysis_job(
    db_session: Session,
) -> None:
    src1 = Source(
        id="src_a",
        nome="Veículo Demo A",
        url_rss="https://demo.local/a",
        categoria_editorial="grande_midia_liberal",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Liberal fictícia",
        descricao="Demo A",
        is_demo=True,
    )
    src2 = Source(
        id="src_b",
        nome="Veículo Demo B",
        url_rss="https://demo.local/b",
        categoria_editorial="imprensa_popular_sindical_esquerda",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Popular fictícia",
        descricao="Demo B",
        is_demo=True,
    )
    event = Event(
        id="evt-resumable-1",
        titulo_provisorio="Greve no transporte de São Paulo",
        resumo="Disputa sobre paralisação em SP",
        periodo_inicio=datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc),
        periodo_fim=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        score_coesao=0.91,
        tema="trabalho",
        local="São Paulo, Brasil",
        lat=-23.5505,
        lon=-46.6333,
        is_demo=True,
    )
    art1 = Article(
        id="art-job-1",
        source_id=src1.id,
        event_id=event.id,
        titulo="Paralisação em SP gera perdas no comércio",
        url_canonica="https://demo.local/a/1",
        guid="ga-1",
        veiculo=src1.nome,
        texto_limpo=SAMPLE_SOURCE_TEXT,
        resumo="Resumo A",
        idioma="pt",
        hash_conteudo="ha-1",
        metodo_coleta="rss_full",
        metadados={},
        is_demo=True,
    )
    art2_text = (
        "Em assembleia histórica com milhares de trabalhadores na capital paulista, "
        "o Sindicato dos Metroviários e a Central Única dos Trabalhadores decretaram greve "
        "contra a terceirização e o arrocho salarial."
    )
    art2 = Article(
        id="art-job-2",
        source_id=src2.id,
        event_id=event.id,
        titulo="Metroviários decretam greve contra terceirização",
        url_canonica="https://demo.local/b/1",
        guid="gb-1",
        veiculo=src2.nome,
        texto_limpo=art2_text,
        resumo="Resumo B",
        idioma="pt",
        hash_conteudo="hb-1",
        metodo_coleta="rss_full",
        metadados={},
        is_demo=True,
    )
    db_session.add_all([src1, src2, event, art1, art2])
    db_session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/props"):
            return httpx.Response(200, json={"model_alias": "Meta-Llama-3.1-8B-Instruct-Q4_K_M"})
        body = json.loads(request.content.decode("utf-8"))
        user_msg = body["messages"][-1]["content"]

        if "art-job-1" in user_msg and "ETAPA 3.1" not in user_msg:
            p1 = {
                "central_thesis": "Foco nas perdas comerciais.",
                "valued_actors": ["FIESP"],
                "devalued_actors": ["Sindicato"],
                "ideological_vocabulary": ["perdas"],
                "privileged_sources": ["FIESP"],
                "likely_omissions": ["Salários"],
                "state_framing": "sem_evidencia_suficiente",
                "market_framing": "Prioridade ao comércio.",
                "labor_framing": "Greve vista como custo.",
                "protest_framing": "Atrasos no deslocamento.",
                "political_effect": "Desgaste da greve.",
                "evidence_quotes": [
                    {
                        "quote": "o setor de comércio e serviços pode registrar perdas superiores a R$ 120 milhões",
                        "context": "Cálculo da FIESP",
                    }
                ],
            }
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(p1)}}]})

        if "art-job-2" in user_msg and "ETAPA 3.1" not in user_msg:
            p2 = {
                "central_thesis": "Foco na mobilização contra terceirização.",
                "valued_actors": ["Sindicato dos Metroviários", "CUT"],
                "devalued_actors": ["Empresas terceirizadas"],
                "ideological_vocabulary": ["arrocho salarial"],
                "privileged_sources": ["Assembleia de trabalhadores"],
                "likely_omissions": ["Dados patronais"],
                "state_framing": "sem_evidencia_suficiente",
                "market_framing": "Crítica à terceirização.",
                "labor_framing": "Protagonismo operário.",
                "protest_framing": "Greve legítima.",
                "political_effect": "Fortalecimento da greve.",
                "evidence_quotes": [
                    {
                        "quote": "o Sindicato dos Metroviários e a Central Única dos Trabalhadores decretaram greve",
                        "context": "Decisão da assembleia",
                    }
                ],
            }
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(p2)}}]})

        # Consolidação (Etapa 3.2): LLM tenta auto-reportar confidence=0.12 (que deve ser descartado!)
        consolidation = {
            "factual_anchor": "Metroviários entraram em greve em São Paulo em 28/10/2026.",
            "actors": [
                {
                    "name": "Sindicato dos Metroviários",
                    "type": "sindicato",
                    "role": "Organização sindical dos trabalhadores",
                    "material_interest": "Defesa do salário e emprego público",
                    "relations": [
                        {
                            "target": "FIESP",
                            "relation": "resiste",
                            "evidence": "Confronto em torno da paralisação em São Paulo",
                        }
                    ],
                }
            ],
            "marxist_leninist_analysis": {
                "central_contradiction": "Capital vs. Trabalho no transporte coletivo.",
                "class_relations": "Classe trabalhadora metroviária vs. burguesia comercial e concessionária.",
                "property_and_power": "Disputa sobre terceirização do serviço público.",
                "role_of_state": "sem_evidencia_suficiente",
                "imperialism_or_dependency": "sem_evidencia_suficiente",
                "ideology_and_naturalization": "Interesse empresarial apresentado como interesse geral.",
                "hegemony_and_silenced_voices": "Vozes sindicais contrapostas à FIESP.",
                "forms_of_struggle": "Greve deliberada em assembleia.",
                "immediate_demand": "Suspensão das terceirizações e recomposição salarial.",
                "strategic_perspective": "Transporte público sob controle dos trabalhadores.",
                "limitations_and_uncertainty": ["Análise baseada em duas matérias iniciais."],
            },
            "reader_questions": [
                "Por que o prejuízo comercial recebe mais destaque que a precarização do trabalho?"
            ],
            "data_visualizations": [],
            "confidence": 0.12,
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(consolidation)}}]})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as mock_http:
        llm_client = LlamaCppClient(http_client=mock_http)
        job = create_or_resume_analysis_job(db_session, event.id)
        completed_job = execute_analysis_job(job.id, db=db_session, llm_client=llm_client)

    assert completed_job.status == "completed"
    assert completed_job.articles_done == 2
    assert completed_job.articles_total == 2

    db_session.refresh(event)
    assert event.event_analysis is not None
    # Ambas as citações são reais -> confidence recalculado pelo sistema deve ser 1.0 (e não 0.12 do LLM)
    assert event.event_analysis.confidence == 1.0
    assert event.event_analysis.dossier_payload["confidence"] == 1.0
