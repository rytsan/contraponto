from pathlib import Path
from typing import Dict, Generator
import httpx
import numpy as np
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base
import app.models  # noqa: F401
from app.clustering.embedder import ArticleEmbedder, l2_normalize

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FEEDS_DIR = FIXTURES_DIR / "feeds"
PAGES_DIR = FIXTURES_DIR / "pages"


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Cria banco SQLite 100% em memória isolado por teste."""
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
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def liberal_feed_xml() -> str:
    return (FEEDS_DIR / "sample_liberal_feed.xml").read_text(encoding="utf-8")


@pytest.fixture()
def popular_feed_xml() -> str:
    return (FEEDS_DIR / "sample_popular_feed.xml").read_text(encoding="utf-8")


@pytest.fixture()
def full_article_html() -> str:
    return (PAGES_DIR / "article_full.html").read_text(encoding="utf-8")


@pytest.fixture()
def paywall_article_html() -> str:
    return (PAGES_DIR / "article_paywall.html").read_text(encoding="utf-8")


@pytest.fixture()
def short_article_html() -> str:
    return (PAGES_DIR / "article_short.html").read_text(encoding="utf-8")


@pytest.fixture()
def mock_http_client(
    liberal_feed_xml: str,
    popular_feed_xml: str,
    full_article_html: str,
    paywall_article_html: str,
) -> Generator[httpx.Client, None, None]:
    """Cliente HTTP mockado (sem rede) servindo feeds RSS, robots.txt e páginas HTML locais."""
    etag_state: Dict[str, str] = {
        "https://diariomercantil.demo.local/rss.xml": '"etag-mercantil-v1"',
        "https://vozoperaria.demo.local/rss.xml": '"etag-voz-v1"',
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            if "bloqueado.demo.local" in url:
                return httpx.Response(
                    200,
                    text="User-agent: *\nDisallow: /\n",
                )
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /privado/\nAllow: /\n",
            )

        if url == "https://diariomercantil.demo.local/rss.xml":
            if request.headers.get("If-None-Match") == etag_state[url]:
                return httpx.Response(304)
            return httpx.Response(
                200,
                text=liberal_feed_xml,
                headers={
                    "ETag": etag_state[url],
                    "Last-Modified": "Wed, 28 Oct 2026 12:00:00 GMT",
                },
            )

        if url == "https://vozoperaria.demo.local/rss.xml":
            if request.headers.get("If-None-Match") == etag_state[url]:
                return httpx.Response(304)
            return httpx.Response(
                200,
                text=popular_feed_xml,
                headers={"ETag": etag_state[url]},
            )

        if "artigo-trafilatura" in url:
            return httpx.Response(200, text=full_article_html)

        if "analise-paywall" in url:
            return httpx.Response(200, text=paywall_article_html)

        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        yield client


@pytest.fixture()
def fake_embedder() -> ArticleEmbedder:
    """
    Embedder determinístico para testes offline que atribui vetores próximos
    para artigos sobre o mesmo evento e ortogonais para eventos distintos.
    """
    def _encode(text: str) -> np.ndarray:
        lower = text.lower()
        vec = np.zeros(16, dtype=np.float32)
        if "transporte" in lower or "metroviários" in lower or "metrô" in lower:
            vec[0] = 0.95
            vec[1] = 0.25 if "comércio" in lower or "patronal" in lower else 0.18
            vec[2] = 0.10
        elif "reforma agrária" in lower or "mst" in lower:
            vec[4] = 0.96
            vec[5] = 0.20
        elif "banco central" in lower or "selic" in lower or "juros" in lower:
            vec[8] = 0.94
            vec[9] = 0.22
        else:
            vec[12] = 0.90
            vec[13] = 0.30
        return l2_normalize(vec)

    return ArticleEmbedder(
        model_name="fake-multilingual-minilm-test",
        encode_fn=_encode,
        use_qdrant=False,
    )
