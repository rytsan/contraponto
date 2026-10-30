import json
from typing import Generator, Tuple
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
import pytest
from app.analysis.llm_client import LlamaCppClient
from app.api.routes_analysis import get_llm_client
from app.database import Base, get_db
from app.main import app
from app.models import Article, Event, Source


@pytest.fixture()
def deck_env() -> Generator[Tuple[TestClient, sessionmaker], None, None]:
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
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def _fake_llm_handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith("/v1/chat/completions"):
            content = json.dumps(
                {
                    "nuance_notes": "Destacar na fala a contradição entre subsídio público e lucro privado.",
                    "summary2": "Enquanto o caixa público banca a operação, a escala segue exaustiva.",
                    "deep": "A análise cruzada mostra que a omissão dos subsídios sustenta o discurso de austeridade.",
                },
                ensure_ascii=False,
            )
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
        return httpx.Response(200, json={"status": "ok"})

    mock_http = httpx.Client(transport=httpx.MockTransport(_fake_llm_handler))
    fake_llm = LlamaCppClient(base_url="http://fake-llama.local", http_client=mock_http)

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_llm_client] = lambda: fake_llm
    with TestClient(app) as client:
        yield client, TestingSessionLocal
    app.dependency_overrides.clear()
    mock_http.close()
    Base.metadata.drop_all(bind=engine)


def test_studio_and_live_decks_flow(deck_env: Tuple[TestClient, sessionmaker]) -> None:
    client, _ = deck_env

    # 1. Listagem inicial cria automaticamente o ensaio seed a partir do evento demo
    res = client.get("/decks")
    assert res.status_code == 200
    decks = res.json()
    assert len(decks) >= 1
    seed_id = decks[0]["id"]
    assert decks[0]["modo"] == "ensaio"
    assert decks[0]["slides_count"] >= 4

    # 2. Gerar pauta de Giro Ao Vivo a partir dos eventos do agregador
    live_res = client.post("/decks/from-live-feed?limit=5")
    assert live_res.status_code == 201
    live_deck = live_res.json()
    assert live_deck["modo"] == "live"
    assert len(live_deck["slides"]) >= 1
    assert len(live_deck["ticker_items"]) >= 1

    # 3. Salvar rascunho com campos vazios e event_id inexistente não quebra FK nem retorna 422
    detail = client.get(f"/decks/{seed_id}").json()
    detail["titulo"] = "Ensaio Editado <Com Escaping>"
    detail["event_id"] = "evento-inexistente-orfão"
    detail["kpis"].append({"label": "", "value": "", "color": "evil;position:fixed"})
    detail["slides"][0]["nuance_notes"] = "Nota de nuance ajustada para gravação."
    detail["slides"][0]["links"].append({"label": "Rascunho vazio", "url": "https://"})
    upd = client.put(f"/decks/{seed_id}", json=detail)
    assert upd.status_code == 200
    saved = upd.json()
    assert saved["event_id"] is None
    assert saved["kpis"][-1]["color"] == "var(--amber)"
    assert saved["slides"][0]["nuance_notes"] == "Nota de nuance ajustada para gravação."

    # 4. Rejeita links com javascript: (proteção XSS)
    bad_payload = dict(saved)
    bad_payload["slides"][0]["links"] = [{"label": "XSS", "url": "javascript:alert(1)"}]
    bad_res = client.put(f"/decks/{seed_id}", json=bad_payload)
    assert bad_res.status_code == 422

    # 5. Exportar como HTML autônomo com escaping seguro e cores das barras
    html_res = client.get(f"/decks/{seed_id}/export-html")
    assert html_res.status_code == 200
    assert "&lt;Com Escaping&gt;" in html_res.text
    assert "Nota de nuance ajustada para gravação." in html_res.text
    assert "toggleTicker" in html_res.text

    # 6. Excluir roteiro
    del_res = client.delete(f"/decks/{live_deck['id']}")
    assert del_res.status_code == 204
    assert client.get(f"/decks/{live_deck['id']}").status_code == 404


def test_raw_event_without_dossier_and_integrations(deck_env: Tuple[TestClient, sessionmaker]) -> None:
    client, SessionMaker = deck_env

    # Evento bruto recém-coletado (sem EventAnalysis e com nome de veículo > 160 chars)
    long_veiculo = "Agência Internacional de Monitoramento Econômico e Sindical " * 4
    with SessionMaker() as db:
        src = Source(
            id="src-long",
            nome=long_veiculo[:250],
            url_rss="https://long.demo.local/rss.xml",
            categoria_editorial="independente",
            pais="BR",
            idioma="pt",
            posicao_editorial_declarada="Independente",
            descricao="Fonte de teste",
        )
        ev = Event(
            id="ev-raw-1",
            titulo_provisorio="Evento bruto sem análise de LLM",
            resumo="Resumo factual coletado via RSS.",
            tema="economia",
        )
        art = Article(
            id="art-raw-1",
            source_id="src-long",
            event_id="ev-raw-1",
            titulo="Manchete coletada diretamente do feed RSS",
            url_canonica="https://long.demo.local/noticia-1",
            guid="guid-raw-1",
            veiculo=long_veiculo[:240],
            data_publicacao=None,
            texto_limpo="Texto integral da notícia para fallback.",
            resumo="Resumo curto da notícia.",
            hash_conteudo="hash123",
        )
        db.add_all([src, ev, art])
        db.commit()

    raw_deck_res = client.post("/decks/from-event/ev-raw-1")
    assert raw_deck_res.status_code == 201
    raw_deck = raw_deck_res.json()
    assert len(raw_deck["slides"]) == 1
    assert len(raw_deck["slides"][0]["timestamp"]) <= 160

    # Sugestão de nuance assistida pelo LLM local
    nuance_res = client.post(
        "/decks/suggest-nuance",
        json={
            "deck_title": raw_deck["titulo"],
            "slide": raw_deck["slides"][0],
            "angle_hint": "Ironia sutil",
        },
    )
    assert nuance_res.status_code == 200
    assert "subsídio público" in nuance_res.json()["nuance_notes"]

    # Sincronização em tempo real via WebSocket (Estúdio -> OBS Browser Source)
    with client.websocket_connect("/decks/ws/live") as ws_studio, client.websocket_connect("/decks/ws/live") as ws_obs:
        sync_msg = {"type": "SYNC_STATE", "currentIndex": 2, "drawerOpen": True, "tickerOpen": True}
        ws_studio.send_json(sync_msg)
        received = ws_obs.receive_json()
        assert received["currentIndex"] == 2
        assert received["drawerOpen"] is True
        assert received["tickerOpen"] is True
