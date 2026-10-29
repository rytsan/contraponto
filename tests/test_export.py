import json
from pathlib import Path
from typing import Generator
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app
from app.models import Article, Event, Source
from app.schemas import DossierSchema
from app.collectors.html_extractor import RobotsCache
from app.collectors.rss_collector import RSSCollector
from app.clustering.embedder import ArticleEmbedder
from app.clustering.event_clusterer import EventClusterer, NominatimGeocoderCache
from app.analysis.evidence_verifier import verify_single_quote
from app.analysis.llm_client import (
    LlamaCppClient,
    load_json_schema,
    validate_against_json_schema,
)
from app.api.routes_analysis import get_job_session_factory, get_llm_client


@pytest.fixture()
def integration_env(
    tmp_path: Path,
    mock_http_client: httpx.Client,
    fake_embedder: ArticleEmbedder,
) -> Generator[tuple[TestClient, sessionmaker, httpx.Client, ArticleEmbedder], None, None]:
    """Ambiente completo de integração ponta a ponta em memória, 100% sem rede."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _llama_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/health"):
            return httpx.Response(200, json={"status": "ok"})
        if url.endswith("/props"):
            return httpx.Response(
                200,
                json={"default_generation_settings": {"model": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"}},
            )
        if url.endswith("/v1/chat/completions"):
            body = json.loads(request.content.decode("utf-8"))
            user_prompt = body["messages"][-1]["content"]

            if "TEXTO ORIGINAL DA MATÉRIA:" in user_prompt:
                marker = 'TEXTO ORIGINAL DA MATÉRIA:\n"""\n'
                idx = user_prompt.find(marker)
                raw_text = ""
                if idx != -1:
                    raw_text = user_prompt[idx + len(marker):].split('"""')[0].strip()

                # Extrai 3 trechos literais reais e 1 trecho inventado (25% falso <= 30%, logo não reprocessa,
                # mas obriga o sistema a marcar o 4º trecho como verified=False e recalcular confidence=0.75!)
                sentences = [s.strip() for s in raw_text.replace("\n", " ").split(".") if len(s.strip()) >= 25]
                real_1 = sentences[0] if len(sentences) > 0 else raw_text[:60]
                real_2 = sentences[1] if len(sentences) > 1 else raw_text[:60]
                real_3 = sentences[2] if len(sentences) > 2 else real_1

                bias_payload = {
                    "central_thesis": "Enquadramento estrutural extraído sobre a greve em São Paulo.",
                    "valued_actors": ["Sindicato dos Metroviários"],
                    "devalued_actors": ["Concessionárias privadas"],
                    "ideological_vocabulary": ["movimento paredista", "terceirizações"],
                    "privileged_sources": ["Entidades de classe"],
                    "likely_omissions": ["sem_evidencia_suficiente"],
                    "state_framing": "Atuação judicial com imposição de multa diária.",
                    "market_framing": "Defesa dos contratos de concessão.",
                    "labor_framing": "Mobilização contra arrocho salarial e terceirização.",
                    "protest_framing": "Paralisação de massa no transporte público.",
                    "political_effect": "Explicitação do antagonismo entre lucro privado e serviço público.",
                    "evidence_quotes": [
                        {"quote": real_1, "context": "Primeiro trecho literal real"},
                        {"quote": real_2, "context": "Segundo trecho literal real"},
                        {"quote": real_3, "context": "Terceiro trecho literal real"},
                        {
                            "quote": "Declaração fabricada que jamais constou em nenhuma matéria coletada pelo sistema",
                            "context": "Trecho sintético inventado para teste anti-fabricação",
                        },
                    ],
                }
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": json.dumps(bias_payload, ensure_ascii=False)}}]},
                )

            consolidation_payload = {
                "factual_anchor": "Metroviários e motoristas realizaram greve em São Paulo em 28/10/2026.",
                "actors": [
                    {
                        "name": "Sindicato dos Metroviários",
                        "type": "sindicato",
                        "role": "Direção sindical da categoria",
                        "material_interest": "Barrar terceirizações e recompor salários",
                        "relations": [
                            {
                                "target": "FIESP",
                                "relation": "resiste",
                                "evidence": "Disputa pública em torno da paralisação em São Paulo",
                            }
                        ],
                    },
                    {
                        "name": "FIESP",
                        "type": "empresa",
                        "role": "Federação empresarial paulista",
                        "material_interest": "Manutenção da circulação mercantil e contenção salarial",
                        "relations": [
                            {
                                "target": "Sindicato dos Metroviários",
                                "relation": "enquadra",
                                "evidence": "Divulgação de cálculo de perdas de R$ 120 milhões",
                            }
                        ],
                    },
                ],
                "marxist_leninist_analysis": {
                    "central_contradiction": "Transporte coletivo essencial subordinado à acumulação privada.",
                    "class_relations": "Trabalhadores metroviários versus burguesia concessionária e industrial.",
                    "property_and_power": "Concessões privadas protegidas por subsídios e aparato estatal.",
                    "role_of_state": "Imposição de frota mínima de 80% sob multa de R$ 500 mil.",
                    "imperialism_or_dependency": "sem_evidencia_suficiente",
                    "ideology_and_naturalization": "Apresentação do lucro contratual como equilíbrio técnico.",
                    "hegemony_and_silenced_voices": "Destaque às perdas comerciais na imprensa liberal.",
                    "forms_of_struggle": "Assembleia histórica, piquetes e greve por tempo indeterminado.",
                    "immediate_demand": "Suspensão das terceirizações e reajuste salarial.",
                    "strategic_perspective": "Reestatização sob controle público e social.",
                    "limitations_and_uncertainty": ["Cobertura concentrada no início da paralisação."],
                },
                "reader_questions": [
                    "Quem financia os subsídios das concessionárias privadas de transporte?"
                ],
                "data_visualizations": [],
                "confidence": 0.99,
            }
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": json.dumps(consolidation_payload, ensure_ascii=False)}}]},
            )
        return httpx.Response(404)

    llama_http = httpx.Client(transport=httpx.MockTransport(_llama_handler))
    fake_llm = LlamaCppClient(http_client=llama_http)

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    app.dependency_overrides[get_job_session_factory] = lambda: TestingSessionLocal

    with TestClient(app) as client:
        yield client, TestingSessionLocal, mock_http_client, fake_embedder

    app.dependency_overrides.clear()
    llama_http.close()
    Base.metadata.drop_all(bind=engine)


def test_export_markdown_and_json_formats(integration_env) -> None:
    client, _, _, _ = integration_env

    # Dispara seed sintético via GET /events
    events_resp = client.get("/events")
    assert events_resp.status_code == 200
    demo_id = events_resp.json()["items"][0]["id"]

    # Exportação Markdown
    resp_md = client.get(f"/events/{demo_id}/export?format=markdown")
    assert resp_md.status_code == 200
    assert "text/markdown" in resp_md.headers["content-type"]
    md_text = resp_md.text
    assert "Toda notícia tem enquadramento. Análise sob ótica marxista-leninista." in md_text
    assert "## 01. Fato — Âncora Factual Mínima" in md_text
    assert "## 02. Disputa de Enquadramento" in md_text
    assert "## 03. Mapa de Poder e Relações entre Atores" in md_text
    assert "## 05. Análise Marxista-Leninista" in md_text
    assert "## 06. Registro de Fontes e Auditoria" in md_text
    assert "[VERIFICADO]" in md_text
    assert "[NÃO VERIFICADO]" in md_text
    assert "A análise é interpretativa e não substitui a leitura das fontes originais." in md_text

    # Exportação JSON validada contra Draft 2020-12 e Pydantic
    resp_json = client.get(f"/events/{demo_id}/export?format=json")
    assert resp_json.status_code == 200
    assert "application/json" in resp_json.headers["content-type"]
    exported_dict = resp_json.json()

    event_schema = load_json_schema("event_analysis.json")
    validate_against_json_schema(exported_dict, event_schema)
    parsed_dossier = DossierSchema.model_validate(exported_dict)
    assert parsed_dossier.event_id == demo_id
    assert parsed_dossier.confidence == 0.83


def test_end_to_end_pipeline_and_anti_fabrication_guarantee(
    integration_env,
    tmp_path: Path,
) -> None:
    """
    Teste obrigatório anti-fabricação e integração ponta a ponta:
    Coleta RSS -> Agrupamento -> Análise Assíncrona -> Verificação -> Dossiê.
    Garante que TODO trecho marcado como `verified: true` existe no texto-fonte da matéria
    e que trechos inventados recebem `verified: false` com recálculo exato de `confidence`.
    """
    client, session_factory, rss_http_client, fake_embedder = integration_env

    with session_factory() as db:
        s_lib = Source(
            id="e2e_mercantil",
            nome="Diário Mercantil Demo",
            url_rss="https://diariomercantil.demo.local/rss.xml",
            categoria_editorial="grande_midia_liberal",
            pais="BR",
            idioma="pt",
            posicao_editorial_declarada="Liberal fictícia",
            descricao="Fonte E2E 1",
        )
        s_pop = Source(
            id="e2e_voz_operaria",
            nome="Voz Operária Demo",
            url_rss="https://vozoperaria.demo.local/rss.xml",
            categoria_editorial="imprensa_popular_sindical_esquerda",
            pais="BR",
            idioma="pt",
            posicao_editorial_declarada="Sindical e popular fictícia",
            descricao="Fonte E2E 2",
        )
        db.add_all([s_lib, s_pop])
        db.commit()

        robots = RobotsCache(cache_path=str(tmp_path / "robots_e2e.json"))
        collector = RSSCollector(
            db=db,
            http_client=rss_http_client,
            robots_cache=robots,
            rate_limit_seconds=0.0,
        )
        arts_1 = collector.collect_from_source(s_lib)
        arts_2 = collector.collect_from_source(s_pop)
        assert len(arts_1) == 3
        assert len(arts_2) == 1

        clusterer = EventClusterer(
            db=db,
            embedder=fake_embedder,
            geocoder=NominatimGeocoderCache(
                cache_path=str(tmp_path / "geo_e2e.json"),
                enabled=True,
                geocode_fn=lambda loc: (-23.5505, -46.6333) if "São Paulo" in loc else None,
            ),
            similarity_threshold=0.82,
        )
        events = clusterer.cluster_articles()
        strike_event = next(e for e in events if len(e.articles) >= 2)
        strike_event_id = strike_event.id

    # Dispara análise assíncrona via API
    resp_analyze = client.post(f"/events/{strike_event_id}/analyze")
    assert resp_analyze.status_code == 202
    assert resp_analyze.json()["status"] == "queued"

    resp_status = client.get(f"/events/{strike_event_id}/analysis-status")
    assert resp_status.status_code == 200
    assert resp_status.json()["status"] == "completed"

    # Recupera dossiê consolidado
    resp_dossier = client.get(f"/events/{strike_event_id}/dossier")
    assert resp_dossier.status_code == 200
    dossier = resp_dossier.json()

    # 3 citações reais e 1 fabricada por matéria -> confidence recalculado deve ser 0.75 (descartando 0.99 do LLM)
    assert dossier["confidence"] == 0.75

    # Auditoria anti-fabricação estrita sobre todas as matérias do evento
    with session_factory() as db:
        all_articles = {
            a.id: f"{a.titulo}\n{a.resumo}\n{a.texto_limpo}"
            for a in db.query(Article).all()
        }

    verified_count = 0
    unverified_count = 0
    for pair in dossier["coverage_pairs"]:
        article_source_text = all_articles[pair["article_id"]]
        for eq in pair["evidence_quotes"]:
            exists_in_source, score = verify_single_quote(eq["quote"], article_source_text)
            if eq["verified"]:
                verified_count += 1
                assert exists_in_source is True, (
                    f"Violação anti-fabricação! Trecho marcado verified=True não existe na fonte: {eq['quote']}"
                )
                assert score >= 92.0
            else:
                unverified_count += 1
                assert exists_in_source is False

    assert verified_count == 6
    assert unverified_count == 2


def test_cross_contract_and_no_prohibited_placeholders() -> None:
    """
    Garante alinhamento estrutural de contratos e ausência de placeholders proibidos
    ('# TODO', '// implementar lógica aqui', 'restante igual ao anterior') no código-fonte.
    """
    project_root = Path(__file__).resolve().parents[1]
    prohibited_markers = [
        "# " + "TODO",
        "// " + "implementar lógica aqui",
        "restante " + "igual ao anterior",
    ]

    checked_files = 0
    for folder in ("app", "frontend/src"):
        base = project_root / folder
        for file_path in base.rglob("*"):
            if file_path.is_file() and file_path.suffix in {".py", ".js", ".svelte", ".json", ".css"}:
                content = file_path.read_text(encoding="utf-8")
                checked_files += 1
                for marker in prohibited_markers:
                    assert marker not in content, f"Placeholder proibido '{marker}' encontrado em {file_path}"

    assert checked_files >= 30

    # Verifica que todas as chaves obrigatórias do JSON Schema do Dossiê existem no componente api.js do frontend
    event_schema = load_json_schema("event_analysis.json")
    frontend_api_js = (project_root / "frontend" / "src" / "lib" / "api.js").read_text(encoding="utf-8")
    for required_key in event_schema["required"]:
        assert f"{required_key}:" in frontend_api_js or f'"{required_key}"' in frontend_api_js, (
            f"Campo obrigatório '{required_key}' do schema ausente no contrato do frontend"
        )
