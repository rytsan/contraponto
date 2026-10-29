import hashlib
import json
import re
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
import httpx
import trafilatura
from app.config import settings

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "dclid",
    "msclkid",
    "twclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "yclid",
    "_ga",
    "_gl",
    "ref",
    "ref_src",
    "ref_url",
}

PAYWALL_PATTERNS = [
    re.compile(r"exclusivo\s+para\s+assinantes", re.IGNORECASE),
    re.compile(r"conte[uú]do\s+restrito\s+a\s+assinantes", re.IGNORECASE),
    re.compile(r"assine\s+para\s+continuar\s+lendo", re.IGNORECASE),
    re.compile(r"subscribe\s+to\s+continue\s+reading", re.IGNORECASE),
    re.compile(r"this\s+article\s+is\s+for\s+subscribers\s+only", re.IGNORECASE),
    re.compile(r'class=["\'][^"\']*(?:paywall|piano-paywall|subscriber-wall|metered-content)[^"\']*["\']', re.IGNORECASE),
    re.compile(r'id=["\'][^"\']*(?:paywall|paywall-banner|subscription-gate)[^"\']*["\']', re.IGNORECASE),
]

MIN_CLEAN_TEXT_CHARS = 500
ROBOTS_TTL_SECONDS = 86400  # 24 horas


def normalize_url(url: str) -> str:
    """Normaliza URL removendo fragmentos e parâmetros de rastreio (utm_*, fbclid, etc.)."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    filtered_query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    filtered_query.sort(key=lambda item: item[0])
    query_str = urlencode(filtered_query)

    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    return urlunparse((scheme, netloc, path, "", query_str, ""))


def compute_content_hash(title: str, text: str) -> str:
    """Calcula hash SHA-256 normalizado a partir do título e texto limpo."""
    normalized = re.sub(r"\s+", " ", f"{title.strip()} || {text.strip()}").lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def detect_paywall(html: str) -> bool:
    """Detecta sinais explícitos de paywall no HTML bruto."""
    if not html:
        return False
    for pattern in PAYWALL_PATTERNS:
        if pattern.search(html):
            return True
    return False


class RobotsCache:
    """Gerenciador de respeito ao robots.txt com cache local e revalidação a cada 24h."""

    def __init__(
        self,
        cache_path: str = ".robots_cache.json",
        ttl_seconds: int = ROBOTS_TTL_SECONDS,
        user_agent: str = "ContrapontoBot",
    ) -> None:
        self.cache_path = Path(cache_path)
        self.ttl_seconds = ttl_seconds
        self.user_agent = user_agent
        self._memory_cache: Dict[str, Dict[str, object]] = {}
        self._load_disk_cache()

    def _load_disk_cache(self) -> None:
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._memory_cache = data
            except Exception:
                self._memory_cache = {}

    def _save_disk_cache(self) -> None:
        try:
            self.cache_path.write_text(
                json.dumps(self._memory_cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def can_fetch(
        self,
        url: str,
        client: Optional[httpx.Client] = None,
        now_ts: Optional[float] = None,
    ) -> bool:
        """Verifica se o User-Agent pode acessar a URL segundo o robots.txt do domínio."""
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return True
        origin = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = f"{origin}/robots.txt"
        current_time = now_ts if now_ts is not None else time.time()

        entry = self._memory_cache.get(origin)
        robots_txt: Optional[str] = None
        if entry and isinstance(entry.get("fetched_at"), (int, float)):
            age = current_time - float(entry["fetched_at"])  # type: ignore[arg-type]
            if age < self.ttl_seconds:
                robots_txt = str(entry.get("content", ""))

        if robots_txt is None:
            robots_txt = self._fetch_robots_txt(robots_url, client=client)
            self._memory_cache[origin] = {
                "fetched_at": current_time,
                "content": robots_txt,
            }
            self._save_disk_cache()

        if not robots_txt.strip():
            return True

        parser = RobotFileParser()
        parser.parse(robots_txt.splitlines())
        return parser.can_fetch(self.user_agent, url)

    def _fetch_robots_txt(
        self,
        robots_url: str,
        client: Optional[httpx.Client] = None,
    ) -> str:
        own_client = client is None
        http_client = client or httpx.Client(
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        try:
            resp = http_client.get(robots_url)
            if resp.status_code == 200 and resp.text:
                return resp.text
            return ""
        except Exception:
            return ""
        finally:
            if own_client:
                http_client.close()


def extract_clean_text_from_html(
    html: str,
    url: Optional[str] = None,
) -> Tuple[Optional[str], bool]:
    """
    Extrai texto limpo de um HTML usando trafilatura.
    Retorna (texto_extraido_ou_None, is_paywall).
    Se detectar paywall ou o texto tiver menos de 500 caracteres, retorna (None, is_paywall).
    """
    if not html or not html.strip():
        return None, False

    is_paywall = detect_paywall(html)
    if is_paywall:
        return None, True

    extracted = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    )
    if not extracted:
        return None, False

    cleaned = extracted.strip()
    if len(cleaned) < MIN_CLEAN_TEXT_CHARS:
        return None, False

    return cleaned, False


def fetch_and_extract_article(
    url: str,
    rss_summary: str,
    rss_content: Optional[str] = None,
    client: Optional[httpx.Client] = None,
    robots_cache: Optional[RobotsCache] = None,
    max_retries: int = 2,
) -> Tuple[str, str, Dict[str, object]]:
    """
    Determina o texto limpo e o metodo_coleta ('rss_full' | 'trafilatura' | 'rss_summary')
    respeitando a política de paywall e o limite mínimo de 500 caracteres.
    Nunca simula texto completo.
    """
    summary_clean = re.sub(r"<[^>]+>", " ", rss_summary or "").strip()
    summary_clean = re.sub(r"\s+", " ", summary_clean)

    if rss_content:
        rss_text_clean = re.sub(r"<[^>]+>", " ", rss_content).strip()
        rss_text_clean = re.sub(r"\s+", " ", rss_text_clean)
        if len(rss_text_clean) >= MIN_CLEAN_TEXT_CHARS and not detect_paywall(rss_content):
            return rss_text_clean, "rss_full", {"paywall_detected": False, "source": "rss_content"}

    checker = robots_cache or RobotsCache()
    if not checker.can_fetch(url, client=client):
        return (
            summary_clean,
            "rss_summary",
            {"paywall_detected": False, "robots_blocked": True},
        )

    own_client = client is None
    http_client = client or httpx.Client(
        timeout=settings.REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": "ContrapontoBot/1.0 (+http://localhost:8000)",
        },
    )

    last_error: Optional[str] = None
    try:
        for attempt in range(max_retries + 1):
            try:
                resp = http_client.get(url)
                if resp.status_code in (401, 402, 403):
                    return (
                        summary_clean,
                        "rss_summary",
                        {
                            "paywall_detected": True,
                            "http_status": resp.status_code,
                        },
                    )
                if resp.status_code >= 400:
                    last_error = f"HTTP {resp.status_code}"
                    break

                extracted_text, is_paywall = extract_clean_text_from_html(resp.text, url=url)
                if is_paywall:
                    return (
                        summary_clean,
                        "rss_summary",
                        {"paywall_detected": True, "http_status": resp.status_code},
                    )
                if extracted_text and len(extracted_text) >= MIN_CLEAN_TEXT_CHARS:
                    return (
                        extracted_text,
                        "trafilatura",
                        {"paywall_detected": False, "http_status": resp.status_code},
                    )
                return (
                    summary_clean,
                    "rss_summary",
                    {
                        "paywall_detected": False,
                        "short_or_empty_extraction": True,
                        "http_status": resp.status_code,
                    },
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    time.sleep(0.1)
    finally:
        if own_client:
            http_client.close()

    return (
        summary_clean,
        "rss_summary",
        {"paywall_detected": False, "fetch_error": last_error},
    )
