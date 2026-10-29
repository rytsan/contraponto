from pathlib import Path
import httpx
from sqlalchemy.orm import Session
from app.models import Article, Source
from app.collectors.html_extractor import RobotsCache, compute_content_hash, normalize_url
from app.collectors.rss_collector import RSSCollector, is_duplicate_article


def test_normalize_url_strips_tracking_params_and_fragments() -> None:
    raw = (
        "https://diariomercantil.demo.local/economia/greve-transporte-sp/"
        "?utm_source=rss&utm_medium=feed&id=42&fbclid=12345#topo"
    )
    normalized = normalize_url(raw)
    assert normalized == "https://diariomercantil.demo.local/economia/greve-transporte-sp?id=42"


def test_rss_collector_parses_local_feed_and_assigns_collection_methods(
    db_session: Session,
    mock_http_client: httpx.Client,
    tmp_path: Path,
) -> None:
    source = Source(
        id="mercantil_demo",
        nome="Diário Mercantil Demo",
        url_rss="https://diariomercantil.demo.local/rss.xml",
        categoria_editorial="grande_midia_liberal",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Liberal fictícia",
        descricao="Fonte sintética de teste",
        is_demo=True,
    )
    db_session.add(source)
    db_session.commit()

    robots_cache = RobotsCache(cache_path=str(tmp_path / "robots.json"))
    collector = RSSCollector(
        db=db_session,
        http_client=mock_http_client,
        robots_cache=robots_cache,
        rate_limit_seconds=0.0,
    )

    articles = collector.collect_from_source(source)
    assert len(articles) == 3

    by_guid = {a.guid: a for a in articles}

    art_full = by_guid["guid-mercantil-greve-sp-001"]
    assert art_full.metodo_coleta == "rss_full"
    assert len(art_full.texto_limpo) >= 500
    assert "utm_source" not in art_full.url_canonica
    assert "fbclid" not in art_full.url_canonica

    art_trafilatura = by_guid["guid-mercantil-trafilatura-002"]
    assert art_trafilatura.metodo_coleta == "trafilatura"
    assert len(art_trafilatura.texto_limpo) >= 500
    assert "escala 6x1" in art_trafilatura.texto_limpo.lower()

    art_paywall = by_guid["guid-mercantil-paywall-003"]
    assert art_paywall.metodo_coleta == "rss_summary"
    assert art_paywall.metadados.get("paywall_detected") is True
    assert "Resumo público do RSS" in art_paywall.texto_limpo


def test_rss_collector_deduplication_by_url_guid_and_hash(
    db_session: Session,
    mock_http_client: httpx.Client,
    liberal_feed_xml: str,
    tmp_path: Path,
) -> None:
    source = Source(
        id="mercantil_demo",
        nome="Diário Mercantil Demo",
        url_rss="https://diariomercantil.demo.local/rss.xml",
        categoria_editorial="grande_midia_liberal",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Liberal fictícia",
        descricao="Fonte sintética de teste",
    )
    db_session.add(source)
    db_session.commit()

    robots_cache = RobotsCache(cache_path=str(tmp_path / "robots.json"))
    collector = RSSCollector(
        db=db_session,
        http_client=mock_http_client,
        robots_cache=robots_cache,
        rate_limit_seconds=0.0,
    )

    first_batch = collector.parse_and_store_feed(source, liberal_feed_xml, client=mock_http_client)
    assert len(first_batch) == 3

    second_batch = collector.parse_and_store_feed(source, liberal_feed_xml, client=mock_http_client)
    assert len(second_batch) == 0
    assert db_session.query(Article).count() == 3

    first_article = first_batch[0]
    same_hash = compute_content_hash(first_article.titulo, first_article.texto_limpo)
    assert is_duplicate_article(
        db_session,
        url_canonica="https://outro-dominio.demo.local/copia-identica",
        guid="guid-totalmente-novo-999",
        hash_conteudo=same_hash,
    )


def test_rss_collector_conditional_get_304_and_robots_disallow(
    db_session: Session,
    mock_http_client: httpx.Client,
    tmp_path: Path,
) -> None:
    source = Source(
        id="mercantil_demo",
        nome="Diário Mercantil Demo",
        url_rss="https://diariomercantil.demo.local/rss.xml",
        categoria_editorial="grande_midia_liberal",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Liberal fictícia",
        descricao="Fonte sintética de teste",
    )
    blocked_source = Source(
        id="bloqueado_demo",
        nome="Veículo Bloqueado por Robots",
        url_rss="https://bloqueado.demo.local/rss.xml",
        categoria_editorial="outros",
        pais="BR",
        idioma="pt",
        posicao_editorial_declarada="Fictícia",
        descricao="Bloqueado no robots.txt",
    )
    db_session.add_all([source, blocked_source])
    db_session.commit()

    robots_cache = RobotsCache(cache_path=str(tmp_path / "robots.json"))
    collector = RSSCollector(
        db=db_session,
        http_client=mock_http_client,
        robots_cache=robots_cache,
        rate_limit_seconds=0.0,
    )

    first_run = collector.collect_from_source(source)
    assert len(first_run) == 3
    assert source.etag == '"etag-mercantil-v1"'

    second_run = collector.collect_from_source(source)
    assert len(second_run) == 0

    blocked_run = collector.collect_from_source(blocked_source)
    assert len(blocked_run) == 0
