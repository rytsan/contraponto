import re
from typing import Any, Dict, List, Tuple
from rapidfuzz import fuzz
from app.schemas import CoveragePairSchema, EvidenceQuoteLLM, EvidenceQuoteSchema

VERIFICATION_THRESHOLD = 92.0
MAX_UNVERIFIED_RATIO = 0.30


def normalize_text_for_fuzzy(text: str) -> str:
    """Normaliza espaços, quebras de linha e aspas tipográficas para comparação fuzzy."""
    if not text:
        return ""
    replaced = (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", "-")
        .replace("–", "-")
    )
    return re.sub(r"\s+", " ", replaced).strip().lower()


def verify_single_quote(
    quote: str,
    source_text: str,
    threshold: float = VERIFICATION_THRESHOLD,
) -> Tuple[bool, float]:
    """
    Compara um trecho de evidence_quotes com o texto original armazenado da matéria
    usando rapidfuzz.fuzz.partial_ratio (limiar >= 92, normalizado).
    Retorna (verified, score).
    """
    norm_quote = normalize_text_for_fuzzy(quote)
    norm_source = normalize_text_for_fuzzy(source_text)

    if not norm_quote or not norm_source:
        return False, 0.0

    # Trechos excessivamente curtos (< 8 caracteres) ou string reservada não contam como citação literal
    if len(norm_quote) < 8 or norm_quote == "sem_evidencia_suficiente":
        return False, 0.0

    if norm_quote in norm_source:
        return True, 100.0

    score = float(fuzz.partial_ratio(norm_quote, norm_source))
    return (score >= threshold), score


def verify_article_quotes(
    quotes: List[EvidenceQuoteLLM],
    source_text: str,
    threshold: float = VERIFICATION_THRESHOLD,
    max_unverified_ratio: float = MAX_UNVERIFIED_RATIO,
) -> Tuple[List[EvidenceQuoteSchema], float, bool]:
    """
    Verifica programaticamente todas as citações de uma matéria (Etapa 3.3).
    Retorna:
      - lista de EvidenceQuoteSchema com campo `verified` preenchido;
      - proporção de citações verificadas (0.0 a 1.0);
      - `needs_reprocess`: True se mais de 30% dos trechos ficarem `verified: False`.
    """
    if not quotes:
        return [], 0.0, True

    verified_list: List[EvidenceQuoteSchema] = []
    verified_count = 0

    for item in quotes:
        is_ok, _ = verify_single_quote(item.quote, source_text, threshold=threshold)
        if is_ok:
            verified_count += 1
        verified_list.append(
            EvidenceQuoteSchema(
                quote=item.quote,
                context=item.context,
                verified=is_ok,
            )
        )

    total = len(verified_list)
    verified_ratio = round(verified_count / total, 4) if total > 0 else 0.0
    unverified_ratio = (total - verified_count) / total if total > 0 else 1.0
    needs_reprocess = unverified_ratio > max_unverified_ratio

    return verified_list, verified_ratio, needs_reprocess


def recalculate_dossier_confidence(coverage_pairs: List[CoveragePairSchema]) -> float:
    """
    Recalcula programaticamente o campo `confidence` final do dossiê:
    trechos verificados ÷ total de trechos (2 casas decimais).
    O valor auto-reportado pelo LLM é sempre descartado.
    """
    total_quotes = 0
    verified_quotes = 0

    for pair in coverage_pairs:
        for eq in pair.evidence_quotes:
            total_quotes += 1
            if eq.verified:
                verified_quotes += 1

    if total_quotes == 0:
        return 0.0

    return round(verified_quotes / total_quotes, 2)


def verify_dossier_payload_quotes(
    dossier_dict: Dict[str, Any],
    articles_text_by_id: Dict[str, str],
    threshold: float = VERIFICATION_THRESHOLD,
) -> Dict[str, Any]:
    """
    Revalida todas as citações de um dicionário de dossiê contra os textos originais
    das matérias e recalcula o campo `confidence` programaticamente.
    """
    total_quotes = 0
    verified_quotes = 0

    for pair in dossier_dict.get("coverage_pairs", []):
        art_id = str(pair.get("article_id", ""))
        source_text = articles_text_by_id.get(art_id, "")
        for eq in pair.get("evidence_quotes", []):
            quote_str = str(eq.get("quote", ""))
            is_ok, _ = verify_single_quote(quote_str, source_text, threshold=threshold)
            eq["verified"] = bool(is_ok)
            total_quotes += 1
            if is_ok:
                verified_quotes += 1

    dossier_dict["confidence"] = round(verified_quotes / total_quotes, 2) if total_quotes > 0 else 0.0
    return dossier_dict
