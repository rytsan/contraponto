import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import feedparser
import httpx
import yaml
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Source
from app.schemas import SourceBase, SourceCheckItem, SourceCreate


def _detect_pending_comments(yaml_path: Path) -> Dict[str, bool]:
    """Identifica quais fontes possuem a anotação '# feed a verificar' no YAML."""
    pending_by_id: Dict[str, bool] = {}
    if not yaml_path.exists():
        return pending_by_id

    current_id: Optional[str] = None
    for raw_line in yaml_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- id:") or stripped.startswith("id:"):
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                val = parts[1].split("#")[0].strip().strip('"').strip("'")
                current_id = val
                pending_by_id.setdefault(current_id, False)
        if current_id and "# feed a verificar" in raw_line:
            pending_by_id[current_id] = True
    return pending_by_id


def load_sources_from_yaml(yaml_path: Optional[str] = None) -> List[SourceBase]:
    """Lê e valida a lista de fontes definidas em data/sources.yaml."""
    path = Path(yaml_path or settings.SOURCES_YAML_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de fontes não encontrado: {path}")

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_sources = raw_data.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError("O arquivo sources.yaml deve conter uma chave raiz 'sources' com uma lista.")

    validated: List[SourceBase] = []
    seen_ids = set()
    for item in raw_sources:
        source_obj = SourceBase.model_validate(item)
        if source_obj.id in seen_ids:
            raise ValueError(f"ID de fonte duplicado em sources.yaml: {source_obj.id}")
        seen_ids.add(source_obj.id)
        validated.append(source_obj)

    return validated


def sync_sources_to_db(db: Session, yaml_path: Optional[str] = None) -> List[Source]:
    """Sincroniza as fontes do arquivo YAML com a tabela sources no banco de dados."""
    sources_cfg = load_sources_from_yaml(yaml_path)
    persisted: List[Source] = []

    for src in sources_cfg:
        existing = db.query(Source).filter(Source.id == src.id).first()
        if existing is None:
            existing = db.query(Source).filter(Source.url_rss == src.url_rss).first()

        if existing is None:
            new_source = Source(
                id=src.id,
                nome=src.nome,
                url_rss=src.url_rss,
                categoria_editorial=src.categoria_editorial,
                pais=src.pais,
                idioma=src.idioma,
                posicao_editorial_declarada=src.posicao_editorial_declarada,
                descricao=src.descricao,
                ativo=True,
                is_demo=False,
            )
            db.add(new_source)
            persisted.append(new_source)
        else:
            existing.nome = src.nome
            existing.url_rss = src.url_rss
            existing.categoria_editorial = src.categoria_editorial
            existing.pais = src.pais
            existing.idioma = src.idioma
            existing.posicao_editorial_declarada = src.posicao_editorial_declarada
            existing.descricao = src.descricao
            persisted.append(existing)

    db.commit()
    for item in persisted:
        db.refresh(item)
    return persisted


def append_source_to_yaml(source_in: SourceCreate, yaml_path: Optional[str] = None) -> None:
    """Adiciona uma nova fonte ao arquivo sources.yaml preservando comentários existentes."""
    path = Path(yaml_path or settings.SOURCES_YAML_PATH)
    existing_sources = load_sources_from_yaml(str(path))
    for s in existing_sources:
        if s.id == source_in.id or s.url_rss == source_in.url_rss:
            return

    entry_dict = {
        "id": source_in.id,
        "nome": source_in.nome,
        "url_rss": source_in.url_rss,
        "categoria_editorial": source_in.categoria_editorial,
        "pais": source_in.pais,
        "idioma": source_in.idioma,
        "posicao_editorial_declarada": source_in.posicao_editorial_declarada,
        "descricao": source_in.descricao,
    }
    snippet = yaml.safe_dump([entry_dict], allow_unicode=True, sort_keys=False)
    indented_lines = ["  " + line for line in snippet.splitlines()]
    content = path.read_text(encoding="utf-8")
    if not content.endswith("\n"):
        content += "\n"
    content += "\n" + "\n".join(indented_lines) + "\n"
    path.write_text(content, encoding="utf-8")


def check_sources(
    yaml_path: Optional[str] = None,
    timeout: float = 8.0,
    client: Optional[httpx.Client] = None,
) -> Tuple[List[SourceCheckItem], int, int]:
    """
    Testa todas as URLs de sources.yaml e reporta válidas e inválidas.
    Retorna (lista_de_resultados, total_validas, total_invalidas).
    """
    path = Path(yaml_path or settings.SOURCES_YAML_PATH)
    sources = load_sources_from_yaml(str(path))
    pending_map = _detect_pending_comments(path)

    results: List[SourceCheckItem] = []
    valid_count = 0
    invalid_count = 0

    headers = {
        "User-Agent": "ContrapontoBot/1.0 (+http://localhost:8000; leitura-critica-rss)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    }

    own_client = client is None
    http_client = client or httpx.Client(timeout=timeout, follow_redirects=True, headers=headers)

    try:
        for src in sources:
            is_pending = pending_map.get(src.id, False)
            try:
                resp = http_client.get(src.url_rss)
                status_code = resp.status_code
                if 200 <= status_code < 400 and resp.content:
                    parsed = feedparser.parse(resp.content)
                    entries_count = len(parsed.entries)
                    has_feed_meta = bool(getattr(parsed, "feed", None) and parsed.feed.keys())
                    if entries_count > 0 or has_feed_meta:
                        results.append(
                            SourceCheckItem(
                                id=src.id,
                                nome=src.nome,
                                url_rss=src.url_rss,
                                pending_verification_comment=is_pending,
                                valid_schema=True,
                                reachable=True,
                                status_code=status_code,
                                entries_count=entries_count,
                                error=None,
                            )
                        )
                        valid_count += 1
                    else:
                        results.append(
                            SourceCheckItem(
                                id=src.id,
                                nome=src.nome,
                                url_rss=src.url_rss,
                                pending_verification_comment=is_pending,
                                valid_schema=True,
                                reachable=False,
                                status_code=status_code,
                                entries_count=0,
                                error="Resposta HTTP sem estrutura RSS/Atom reconhecida",
                            )
                        )
                        invalid_count += 1
                else:
                    results.append(
                        SourceCheckItem(
                            id=src.id,
                            nome=src.nome,
                            url_rss=src.url_rss,
                            pending_verification_comment=is_pending,
                            valid_schema=True,
                            reachable=False,
                            status_code=status_code,
                            entries_count=0,
                            error=f"HTTP {status_code}",
                        )
                    )
                    invalid_count += 1
            except Exception as exc:
                results.append(
                    SourceCheckItem(
                        id=src.id,
                        nome=src.nome,
                        url_rss=src.url_rss,
                        pending_verification_comment=is_pending,
                        valid_schema=True,
                        reachable=False,
                        status_code=None,
                        entries_count=0,
                        error=str(exc),
                    )
                )
                invalid_count += 1
    finally:
        if own_client:
            http_client.close()

    return results, valid_count, invalid_count


def main(argv: Optional[List[str]] = None) -> int:
    """Ponto de entrada CLI para validação das fontes configuradas."""
    parser = argparse.ArgumentParser(
        description="Carregador e validador de fontes RSS do Contraponto."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Testa todas as URLs de data/sources.yaml e reporta válidas/inválidas.",
    )
    parser.add_argument(
        "--file",
        default=settings.SOURCES_YAML_PATH,
        help="Caminho para o arquivo sources.yaml.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Timeout em segundos por fonte no modo --check.",
    )
    args = parser.parse_args(argv)

    try:
        sources = load_sources_from_yaml(args.file)
    except Exception as exc:
        print(f"[ERRO] Falha ao validar schema de {args.file}: {exc}", file=sys.stderr)
        return 1

    if not args.check:
        print(f"[OK] {len(sources)} fontes carregadas de {args.file}.")
        return 0

    print(f"Verificando {len(sources)} fontes em '{args.file}' (timeout={args.timeout}s)...")
    results, valid_count, invalid_count = check_sources(args.file, timeout=args.timeout)

    for item in results:
        pending_tag = " [# feed a verificar]" if item.pending_verification_comment else ""
        if item.reachable:
            print(
                f"  [VÁLIDA]   {item.id:<20} | HTTP {item.status_code} | "
                f"{item.entries_count:3d} itens | {item.url_rss}{pending_tag}"
            )
        else:
            print(
                f"  [INVÁLIDA] {item.id:<20} | Motivo: {item.error} | "
                f"{item.url_rss}{pending_tag}"
            )

    print(
        f"\nResumo da verificação: {len(results)} fontes no schema | "
        f"{valid_count} acessíveis/válidas | {invalid_count} inacessíveis/inválidas."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
