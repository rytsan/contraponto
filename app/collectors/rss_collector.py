import calendar
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
import feedparser
import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Article, Source, utcnow
from app.collectors.html_extractor import (
    RobotsCache,
    compute_content_hash,
    fetch_and_extract_article,
    normalize_url,
)
from app.collectors.sources_loader import sync_sources_to_db


def _parse_entry_datetime(entry: Any) -> Optional[datetime]:
    """Extrai e normaliza data de publicação de um item do feedparser para UTC."""
    for struct_attr in ("published_parsed", "updated_parsed", "created_parsed"):
        st = getattr(entry, struct_attr, None) or entry.get(struct_attr)
        if st:
            try:
                ts = calendar.timegm(st)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass

    for str_attr in ("published", "updated", "created"):
        raw = getattr(entry, str_attr, None) or entry.get(str_attr)
        if raw and isinstance(raw, str):
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                try:
                    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc)
                except Exception:
                    pass
    return None


def _extract_entry_rss_content(entry: Any) -> Optional[str]:
    """Extrai o conteúdo completo presente na tag content/content:encoded do RSS quando existir."""
    contents = getattr(entry, "content", None) or entry.get("content")
    if isinstance(contents, list) and contents:
        parts = [str(item.get("value", "")) for item in contents if isinstance(item, dict)]
        joined = "\n".join(p for p in parts if p).strip()
        if joined:
            return joined
    return None


def _clean_html_tags(text: str) -> str:
    """Remove tags HTML simples e colapsa espaços em branco."""
    without_tags = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", without_tags).strip()


def is_duplicate_article(
    db: Session,
    url_canonica: str,
    guid: str,
    hash_conteudo: str,
) -> bool:
    """Verifica deduplicação no banco por URL canônica normalizada, GUID ou hash de conteúdo."""
    existing = (
        db.query(Article.id)
        .filter(
            or_(
                Article.url_canonica == url_canonica,
                Article.guid == guid,
                Article.hash_conteudo == hash_conteudo,
            )
        )
        .first()
    )
    return existing is not None


class RSSCollector:
    """Coletor de feeds RSS/Atom com suporte a ETag/Last-Modified, robots.txt, rate limit e deduplicação."""

    def __init__(
        self,
        db: Session,
        http_client: Optional[httpx.Client] = None,
        robots_cache: Optional[RobotsCache] = None,
        rate_limit_seconds: Optional[float] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: int = 2,
    ) -> None:
        self.db = db
        self.http_client = http_client
        self.robots_cache = robots_cache or RobotsCache()
        self.rate_limit_seconds = (
            rate_limit_seconds if rate_limit_seconds is not None else settings.RATE_LIMIT_SECONDS
        )
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.REQUEST_TIMEOUT_SECONDS
        )
        self.max_retries = max_retries

    def collect_all_sources(self, yaml_path: Optional[str] = None) -> List[Article]:
        """Sincroniza sources.yaml e coleta todas as fontes ativas."""
        sources = sync_sources_to_db(self.db, yaml_path=yaml_path)
        collected_articles: List[Article] = []

        for idx, source in enumerate(sources):
            if not source.ativo or source.is_demo:
                continue
            if idx > 0 and self.rate_limit_seconds > 0:
                time.sleep(self.rate_limit_seconds)
            new_items = self.collect_from_source(source)
            collected_articles.extend(new_items)

        return collected_articles

    def collect_from_source(self, source: Source) -> List[Article]:
        """Baixa e processa o feed RSS/Atom de uma única fonte."""
        own_client = self.http_client is None
        client = self.http_client or httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": "ContrapontoBot/1.0 (+http://localhost:8000)",
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            },
        )

        try:
            if not self.robots_cache.can_fetch(source.url_rss, client=client):
                return []

            req_headers: Dict[str, str] = {}
            if source.etag:
                req_headers["If-None-Match"] = source.etag
            if source.last_modified:
                req_headers["If-Modified-Since"] = source.last_modified

            resp: Optional[httpx.Response] = None
            for attempt in range(self.max_retries + 1):
                try:
                    resp = client.get(source.url_rss, headers=req_headers)
                    break
                except Exception:
                    if attempt < self.max_retries:
                        time.sleep(0.1)

            if resp is None:
                return []

            if resp.status_code == 304:
                source.ultima_coleta = utcnow()
                self.db.commit()
                return []

            if resp.status_code >= 400:
                return []

            new_etag = resp.headers.get("ETag") or resp.headers.get("etag")
            new_last_mod = resp.headers.get("Last-Modified") or resp.headers.get("last-modified")
            if new_etag:
                source.etag = new_etag
            if new_last_mod:
                source.last_modified = new_last_mod
            source.ultima_coleta = utcnow()
            self.db.commit()

            return self.parse_and_store_feed(
                source=source,
                raw_xml=resp.text,
                client=client,
            )
        finally:
            if own_client:
                client.close()

    def parse_and_store_feed(
        self,
        source: Source,
        raw_xml: str,
        client: Optional[httpx.Client] = None,
    ) -> List[Article]:
        """Faz o parse de um XML RSS/Atom e persiste artigos inéditos no banco."""
        parsed = feedparser.parse(raw_xml)
        created: List[Article] = []

        for entry in parsed.entries:
            title = _clean_html_tags(str(entry.get("title", "")).strip())
            raw_link = str(entry.get("link", "")).strip()
            if not title or not raw_link:
                continue

            url_canonica = normalize_url(raw_link)
            if not url_canonica:
                continue

            raw_guid = str(entry.get("id") or entry.get("guid") or url_canonica).strip()
            summary_raw = str(entry.get("summary") or entry.get("description") or "").strip()
            summary_clean = _clean_html_tags(summary_raw) or title
            rss_content_raw = _extract_entry_rss_content(entry)

            if (
                self.db.query(Article.id)
                .filter(or_(Article.url_canonica == url_canonica, Article.guid == raw_guid))
                .first()
                is not None
            ):
                continue

            texto_limpo, metodo_coleta, extra_meta = fetch_and_extract_article(
                url=url_canonica,
                rss_summary=summary_clean,
                rss_content=rss_content_raw,
                client=client,
                robots_cache=self.robots_cache,
                max_retries=self.max_retries,
            )

            if not texto_limpo:
                texto_limpo = summary_clean
                metodo_coleta = "rss_summary"

            hash_conteudo = compute_content_hash(title, texto_limpo)
            if is_duplicate_article(self.db, url_canonica, raw_guid, hash_conteudo):
                continue

            author = entry.get("author")
            if author:
                author = _clean_html_tags(str(author))[:255]

            pub_dt = _parse_entry_datetime(entry)
            tags = [
                str(t.get("term", "")).strip()
                for t in (entry.get("tags") or [])
                if isinstance(t, dict) and t.get("term")
            ]

            metadata_payload: Dict[str, Any] = {
                "raw_link": raw_link,
                "tags": tags,
                "categoria_editorial": source.categoria_editorial,
                "posicao_editorial_declarada": source.posicao_editorial_declarada,
                **extra_meta,
            }

            article = Article(
                source_id=source.id,
                titulo=title[:512],
                url_canonica=url_canonica[:1024],
                guid=raw_guid[:1024],
                veiculo=source.nome,
                autor=author,
                data_publicacao=pub_dt,
                data_coleta=utcnow(),
                texto_limpo=texto_limpo,
                resumo=summary_clean,
                idioma=source.idioma,
                hash_conteudo=hash_conteudo,
                metodo_coleta=metodo_coleta,
                metadados=metadata_payload,
                is_demo=False,
            )
            self.db.add(article)
            self.db.commit()
            self.db.refresh(article)
            created.append(article)

        return created


def main() -> None:
    """Executa um ciclo completo de coleta RSS via linha de comando."""
    init_db()
    with SessionLocal() as db:
        collector = RSSCollector(db=db)
        new_articles = collector.collect_all_sources()
        print(f"[Coletor RSS] {len(new_articles)} novos artigos coletados.")


if __name__ == "__main__":
    main()
