from pathlib import Path
import httpx
from app.collectors.html_extractor import (
    MIN_CLEAN_TEXT_CHARS,
    RobotsCache,
    detect_paywall,
    extract_clean_text_from_html,
    fetch_and_extract_article,
)


def test_extract_clean_text_from_full_html_fixture(full_article_html: str) -> None:
    text, is_paywall = extract_clean_text_from_html(
        full_article_html,
        url="https://diariomercantil.demo.local/politica/artigo-trafilatura",
    )
    assert is_paywall is False
    assert text is not None
    assert len(text) >= MIN_CLEAN_TEXT_CHARS
    assert "redução da jornada de trabalho semanal" in text
    assert "Central Única dos Trabalhadores" in text


def test_paywall_html_triggers_rss_summary_fallback(
    paywall_article_html: str,
    mock_http_client: httpx.Client,
    tmp_path: Path,
) -> None:
    assert detect_paywall(paywall_article_html) is True
    text, is_paywall = extract_clean_text_from_html(paywall_article_html)
    assert text is None
    assert is_paywall is True

    robots_cache = RobotsCache(cache_path=str(tmp_path / "robots.json"))
    summary_input = "Resumo original do RSS preservado honestamente sem inventar texto completo."
    clean_text, method, meta = fetch_and_extract_article(
        url="https://diariomercantil.demo.local/economia/analise-paywall",
        rss_summary=summary_input,
        rss_content=None,
        client=mock_http_client,
        robots_cache=robots_cache,
    )
    assert method == "rss_summary"
    assert clean_text == summary_input
    assert meta.get("paywall_detected") is True


def test_short_html_below_500_chars_falls_back_to_rss_summary(short_article_html: str) -> None:
    text, is_paywall = extract_clean_text_from_html(short_article_html)
    assert is_paywall is False
    assert text is None


def test_robots_cache_revalidation_after_24h(
    mock_http_client: httpx.Client,
    tmp_path: Path,
) -> None:
    cache_file = tmp_path / "robots_cache.json"
    cache = RobotsCache(cache_path=str(cache_file), ttl_seconds=86400)

    t0 = 1_700_000_000.0
    assert cache.can_fetch(
        "https://diariomercantil.demo.local/economia/artigo",
        client=mock_http_client,
        now_ts=t0,
    ) is True
    assert cache.can_fetch(
        "https://diariomercantil.demo.local/privado/secreto",
        client=mock_http_client,
        now_ts=t0 + 100,
    ) is False
    assert cache.can_fetch(
        "https://bloqueado.demo.local/qualquer",
        client=mock_http_client,
        now_ts=t0,
    ) is False
