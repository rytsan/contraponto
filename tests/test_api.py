import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import Article, Event, Source
from app.analysis.evidence_verifier import verify_single_quote
from app.analysis.llm_client import LlamaCppClient
from app.api.routes_analysis import get_job_session_factory, get_llm_client


@pytest.fixture()
def api_test_env(tmp_path: Path) -> Generator[tuple[TestClient, sessionmaker, Path], None, None]:
    """Configura TestClient com banco em memória e fake de llama-server sem acesso à rede."""
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

    temp_sources_yaml = tmp_path / "sources.yaml"
    orig_sources_yaml = Path(settings.SOURCES_YAML_PATH)
    if orig_sources_yaml.exists():
        shutil.copy(orig_sources_yaml, temp_sources_yaml)
    orig_setting_val = settings.SOURCES_YAML_PATH
    settings.SOURCES_YAML_PATH = str(temp_sources_yaml)

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _llama_fake_handler(request: httpx.Request) -> httpx.Response:
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
                # Extrai primeira frase real do texto da matéria enviado no prompt para garantir citação literal
                marker = 'TEXTO ORIGINAL DA MATÉRIA:\n"""\n'
                idx = user_prompt.find(marker)
                snippet = "Paralisação no transporte"
                if idx != -1:
                    raw_text = user_prompt[idx + len(marker):].split('"""')[0].strip()
                    snippet = raw_text[:95].strip()

                bias_resp = {
                    "central_thesis": "Tese central extraída pelo fake de llama.cpp.",
                    "valued_actors": ["Sindicato Unificado"],
                    "devalued_actors": ["Consórcio ViaPrivada"],
                    "ideological_vocabulary": ["equilíbrio econômico-financeiro"],
                    "privileged_sources": ["Assembleia da categoria"],
                    "likely_omissions": ["sem_evidencia_suficiente"],
                    "state_framing": "Estado aplica multas contra o movimento.",
                    "market_framing": "Concessionárias priorizam dividendos.",
                    "labor_framing": "Trabalhadores resistem à escala 6x1.",
                    "protest_framing": "Greve tratada como instrumento de luta.",
                    "political_effect": "Explicitação do conflito distributivo.",
                    "evidence_quotes": [
                        {
                            "quote": snippet,
                            "context": "Trecho literal extraído da abertura da matéria.",
                        }
                    ],
                }
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": json.dumps(bias_resp, ensure_ascii=False)}}]},
                )

            # Etapa 3.2 — Consolidação do evento
            consolidation_resp = {
                "factual_anchor": "Trabalhadores realizaram paralisação no transporte em São Paulo.",
                "actors": [
                    {
                        "name": "Sindicato Unificado",
                        "type": "sindicato",
                        "role": "Representação dos operadores",
                        "material_interest": "Redução da jornada e fim da terceirização",
                        "relations": [
                            {
                                "target": "Consórcio ViaPrivada",
                                "relation": "resiste",
                                "evidence": "Paralisação aprovada em assembleia",
                            }
                        ],
                    }
                ],
                "marxist_leninist_analysis": {
                    "central_contradiction": "Serviço público socializado vs. apropriação privada de dividendos.",
                    "class_relations": "Operários do transporte vs. burguesia concessionária.",
                    "property_and_power": "Concessão privada subsidiada pelo fundo público.",
                    "role_of_state": "Garantidor dos contratos e repressor da greve.",
                    "imperialism_or_dependency": "sem_evidencia_suficiente",
                    "ideology_and_naturalization": "Naturalização do lucro sob discurso técnico.",
                    "hegemony_and_silenced_voices": "Prioridade às federações empresariais.",
                    "forms_of_struggle": "Greve unificada e assembleia de base.",
                    "immediate_demand": "Fim da escala 6x1 e recomposição salarial.",
                    "strategic_perspective": "Reestatização sob controle operário e popular.",
                    "limitations_and_uncertainty": ["Análise de teste automatizado."],
                },
                "reader_questions": [
                    "Quem controla as planilhas de custos das concessões?"
                ],
                "data_visualizations": [],
                "confidence": 0.45,
            }
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": json.dumps(consolidation_resp, ensure_ascii=False)}}]},
            )
        return httpx.Response(404)

    mock_http = httpx.Client(transport=httpx.MockTransport(_llama_fake_handler))
    fake_llm_client = LlamaCppClient(http_client=mock_http)

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_client] = lambda: fake_llm_client
    app.dependency_overrides[get_job_session_factory] = lambda: TestingSessionLocal

    with TestClient(app) as client:
        yield client, TestingSessionLocal, temp_sources_yaml

    app.dependency_overrides.clear()
    mock_http.close()
    settings.SOURCES_YAML_PATH = orig_setting_val
    Base.metadata.drop_all(bind=engine)


def test_health_endpoint_reports_db_llama_and_qdrant_disabled(api_test_env) -> None:
    client, _, _ = api_test_env
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["llama_server"]["reachable"] is True
    assert data["llama_server"]["model"] == "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
    assert data["qdrant"]["status"] == "disabled"


def test_events_auto_seeds_synthetic_demo_and_respects_anti_fabrication(api_test_env) -> None:
    client, _, _ = api_test_env

    resp_events = client.get("/events")
    assert resp_events.status_code == 200
    payload = resp_events.json()
    assert payload["total"] == 1
    demo_event = payload["items"][0]
    assert demo_event["id"] == "demo-event-transporte-sp-2026"
    assert demo_event["is_demo"] is True
    assert demo_event["has_dossier"] is True

    # Verifica detalhes do evento e dossiê
    resp_dossier = client.get(f"/events/{demo_event['id']}/dossier")
    assert resp_dossier.status_code == 200
    dossier = resp_dossier.json()
    assert dossier["is_demo"] is True
    # 5 citações verificadas de um total de 6 no fixture -> confidence recalculado = 0.83
    assert dossier["confidence"] == 0.83

    # Regra anti-fabricação: toda citação marcada como verified=True deve existir no texto original da matéria
    resp_articles = client.get(f"/articles?event_id={demo_event['id']}")
    assert resp_articles.status_code == 200
    articles_by_id = {}
    for item in resp_articles.json()["items"]:
        full_art = client.get(f"/articles/{item['id']}").json()
        assert full_art["is_demo"] is True
        assert "Demo" in full_art["veiculo"]
        articles_by_id[item["id"]] = f"{full_art['titulo']}\n{full_art['resumo']}\n{full_art['texto_limpo']}"

    for pair in dossier["coverage_pairs"]:
        src_text = articles_by_id[pair["article_id"]]
        for quote_obj in pair["evidence_quotes"]:
            is_real, _ = verify_single_quote(quote_obj["quote"], src_text)
            assert quote_obj["verified"] is is_real


def test_sources_get_and_post_persists_in_db_and_yaml(api_test_env) -> None:
    client, _, temp_sources_yaml = api_test_env

    resp_list = client.get("/sources")
    assert resp_list.status_code == 200
    initial_count = len(resp_list.json())
    assert initial_count >= 15

    new_source = {
        "id": "veiculo_comunitario_teste",
        "nome": "Rádio Comunitária Popular Teste",
        "url_rss": "https://radiocomunitaria.demo.local/feed.xml",
        "categoria_editorial": "imprensa_popular_sindical_esquerda",
        "pais": "BR",
        "idioma": "pt",
        "posicao_editorial_declarada": "Comunicação popular e comunitária",
        "descricao": "Fonte adicionada via POST /sources no teste.",
    }
    resp_post = client.post("/sources", json=new_source)
    assert resp_post.status_code == 201
    created = resp_post.json()
    assert created["id"] == "veiculo_comunitario_teste"

    # Confirma persistência no YAML
    yaml_text = temp_sources_yaml.read_text(encoding="utf-8")
    assert "veiculo_comunitario_teste" in yaml_text
    assert "https://radiocomunitaria.demo.local/feed.xml" in yaml_text


def test_async_analyze_returns_202_and_progresses_to_completed(api_test_env) -> None:
    client, session_factory, _ = api_test_env

    with session_factory() as db:
        src1 = Source(
            id="async_src_1",
            nome="Jornal Comercial Fictício",
            url_rss="https://comercial.demo.local/rss",
            categoria_editorial="grande_midia_liberal",
            pais="BR",
            idioma="pt",
            posicao_editorial_declarada="Liberal fictícia",
            descricao="Fonte 1",
            is_demo=True,
        )
        src2 = Source(
            id="async_src_2",
            nome="Jornal Operário Fictício",
            url_rss="https://operario.demo.local/rss",
            categoria_editorial="imprensa_popular_sindical_esquerda",
            pais="BR",
            idioma="pt",
            posicao_editorial_declarada="Classista fictícia",
            descricao="Fonte 2",
            is_demo=True,
        )
        ev = Event(
            id="evt-async-test-001",
            titulo_provisorio="Disputa sobre jornada de trabalho",
            resumo="Duas coberturas divergentes sobre escala 6x1",
            periodo_inicio=datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc),
            periodo_fim=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
            score_coesao=0.88,
            tema="trabalho",
            local="São Paulo, Brasil",
            lat=-23.5505,
            lon=-46.6333,
            is_demo=True,
        )
        a1 = Article(
            id="art-async-1",
            source_id=src1.id,
            event_id=ev.id,
            titulo="Empresários criticam redução da jornada semanal",
            url_canonica="https://comercial.demo.local/jornada-1",
            guid="g-async-1",
            veiculo=src1.nome,
            texto_limpo=(
                "Confederações patronais afirmaram nesta quarta-feira que o fim da escala 6x1 "
                "eleva os custos operacionais do setor de comércio e serviços nas grandes capitais."
            ),
            resumo="Empresários criticam fim da escala 6x1.",
            idioma="pt",
            hash_conteudo="h-async-1",
            metodo_coleta="rss_full",
            metadados={},
            is_demo=True,
        )
        a2 = Article(
            id="art-async-2",
            source_id=src2.id,
            event_id=ev.id,
            titulo="Trabalhadores mobilizam atos pelo fim da escala 6x1",
            url_canonica="https://operario.demo.local/jornada-2",
            guid="g-async-2",
            veiculo=src2.nome,
            texto_limpo=(
                "Sindicatos e movimentos de trabalhadores realizaram atos pelo fim da escala 6x1 "
                "e pela redução da jornada para 36 horas semanais sem redução de salário."
            ),
            resumo="Atos pelo fim da escala 6x1.",
            idioma="pt",
            hash_conteudo="h-async-2",
            metodo_coleta="rss_full",
            metadados={},
            is_demo=True,
        )
        db.add_all([src1, src2, ev, a1, a2])
        db.commit()

    # POST /events/{id}/analyze responde imediatamente 202 com status="queued"
    resp_trigger = client.post("/events/evt-async-test-001/analyze")
    assert resp_trigger.status_code == 202
    trigger_data = resp_trigger.json()
    assert "analysis_id" in trigger_data
    assert trigger_data["status"] == "queued"

    # Após a execução da BackgroundTask no TestClient, o status progride até "completed"
    resp_status = client.get("/events/evt-async-test-001/analysis-status")
    assert resp_status.status_code == 200
    status_data = resp_status.json()
    assert status_data["status"] == "completed"
    assert status_data["stage"] == "consolidacao"
    assert status_data["articles_done"] == 2
    assert status_data["articles_total"] == 2
    assert status_data["error"] is None

    # Dossiê gerado disponível com confidence recalculado = 1.0 (e não 0.45 do fake LLM)
    resp_dossier = client.get("/events/evt-async-test-001/dossier")
    assert resp_dossier.status_code == 200
    dossier = resp_dossier.json()
    assert dossier["event_id"] == "evt-async-test-001"
    assert dossier["confidence"] == 1.0
    assert len(dossier["coverage_pairs"]) == 2
    assert all(
        eq["verified"] is True
        for pair in dossier["coverage_pairs"]
        for eq in pair["evidence_quotes"]
    )
