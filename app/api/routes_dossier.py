import json
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Event
from app.schemas import DossierSchema
from app.api.routes_events import build_verified_dossier_for_event, ensure_demo_seed

router = APIRouter(prefix="/events", tags=["dossier"])

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"


def render_dossier_markdown(dossier: DossierSchema) -> str:
    """Gera representação editorial completa em Markdown de um Dossiê de Contradição."""
    lines = []
    demo_badge = " `[DEMO — DADOS 100% SINTÉTICOS]`" if dossier.is_demo else ""
    title = dossier.title or f"Dossiê do Evento {dossier.event_id}"

    lines.append(f"# {title}{demo_badge}")
    lines.append("")
    lines.append("> **Toda notícia tem enquadramento. Análise sob ótica marxista-leninista.**")
    lines.append("")
    lines.append("## 01. Fato — Âncora Factual Mínima")
    lines.append("")
    lines.append(f"- **ID do Evento:** `{dossier.event_id}`")
    lines.append(f"- **Tema:** `{dossier.theme}`")
    lines.append(f"- **Local:** {dossier.location or 'Não especificado'}")
    if dossier.coordinates.lat is not None and dossier.coordinates.lon is not None:
        lines.append(f"- **Coordenadas:** `{dossier.coordinates.lat}, {dossier.coordinates.lon}`")
    lines.append(f"- **Confiança Verificada (Etapa 3.3):** `{int(round(dossier.confidence * 100))}%` ({dossier.confidence:.2f})")
    lines.append("")
    lines.append(f"**Âncora Factual Mínima:** {dossier.factual_anchor}")
    lines.append("")
    lines.append("*Aviso: Âncora factual mínima não é neutralidade. É apenas o núcleo verificável comum entre as fontes.*")
    lines.append("")

    lines.append("## 02. Disputa de Enquadramento")
    lines.append("")
    lines.append("> *Quem aparece como sujeito e quem aparece como problema?*")
    lines.append("")
    for idx, pair in enumerate(dossier.coverage_pairs, start=1):
        lines.append(f"### {idx}. {pair.source}")
        lines.append(f"- **Manchete:** {pair.headline}")
        lines.append(f"- **Posição Editorial Declarada:** {pair.source_position}")
        lines.append(f"- **URL:** {pair.url}")
        lines.append(f"- **Tese Central:** {pair.central_thesis}")
        lines.append(f"- **Atores Valorizados:** {', '.join(pair.valued_actors) or 'Nenhum'}")
        lines.append(f"- **Atores Desvalorizados:** {', '.join(pair.devalued_actors) or 'Nenhum'}")
        lines.append(f"- **Vocabulário Ideológico:** {', '.join(pair.ideological_vocabulary) or 'Nenhum'}")
        lines.append(f"- **Fontes Privilegiadas:** {', '.join(pair.privileged_sources) or 'Nenhuma'}")
        lines.append(f"- **Omissões Prováveis:** {', '.join(pair.likely_omissions) or 'Nenhuma'}")
        lines.append(f"- **Enquadramento do Estado:** {pair.state_framing}")
        lines.append(f"- **Enquadramento do Mercado:** {pair.market_framing}")
        lines.append(f"- **Enquadramento do Trabalho:** {pair.labor_framing}")
        lines.append(f"- **Enquadramento de Protesto/Luta:** {pair.protest_framing}")
        lines.append(f"- **Efeito Político Provável:** {pair.political_effect}")
        lines.append("- **Evidências Textuais Citadas:**")
        for eq in pair.evidence_quotes:
            badge = "[VERIFICADO]" if eq.verified else "[NÃO VERIFICADO]"
            lines.append(f'  - `{badge}` "{eq.quote}" — *{eq.context}*')
        lines.append("")

    lines.append("## 03. Mapa de Poder e Relações entre Atores")
    lines.append("")
    for actor in dossier.actors:
        lines.append(f"- **{actor.name}** (`{actor.type}`) — Papel: {actor.role}")
        lines.append(f"  - *Interesse Material:* {actor.material_interest}")
        for rel in actor.relations:
            lines.append(f"  - *Relação:* `{rel.relation}` -> **{rel.target}** ({rel.evidence})")
    lines.append("")

    lines.append("## 04. Dados Extraídos")
    lines.append("")
    if not dossier.data_visualizations:
        lines.append("Dados insuficientes para visualização honesta.")
    else:
        for viz in dossier.data_visualizations:
            lines.append(f"### {viz.title} (`{viz.type}`)")
            lines.append(f"{viz.description}")
            for lbl, val in zip(viz.labels, viz.values):
                lines.append(f"- **{lbl}:** {val}")
            lines.append(f"- *Artigos de origem:* `{', '.join(viz.source_article_ids)}`")
            lines.append("")

    ml = dossier.marxist_leninist_analysis
    lines.append("## 05. Análise Marxista-Leninista")
    lines.append("")
    lines.append(f"- **Contradição Central:** {ml.central_contradiction}")
    lines.append(f"- **Relações de Classe:** {ml.class_relations}")
    lines.append(f"- **Propriedade e Poder:** {ml.property_and_power}")
    lines.append(f"- **Papel do Estado:** {ml.role_of_state}")
    lines.append(f"- **Imperialismo ou Dependência:** {ml.imperialism_or_dependency}")
    lines.append(f"- **Ideologia e Naturalização:** {ml.ideology_and_naturalization}")
    lines.append(f"- **Hegemonia e Vozes Silenciadas:** {ml.hegemony_and_silenced_voices}")
    lines.append(f"- **Formas de Luta e Organização:** {ml.forms_of_struggle}")
    lines.append(f"- **Demanda Imediata:** {ml.immediate_demand}")
    lines.append(f"- **Perspectiva Estratégica:** {ml.strategic_perspective}")
    if ml.limitations_and_uncertainty:
        lines.append("- **Limites e Incertezas:**")
        for lim in ml.limitations_and_uncertainty:
            lines.append(f"  - {lim}")
    lines.append("")

    lines.append("### Perguntas Críticas ao Leitor")
    for q in dossier.reader_questions:
        lines.append(f"1. {q}")
    lines.append("")

    lines.append("## 06. Registro de Fontes e Auditoria")
    lines.append("")
    if dossier.audit_metadata:
        lines.append(f"- **Data da Análise:** {dossier.audit_metadata.analyzed_at.isoformat()}")
        lines.append(f"- **Modelo Local Utilizado:** `{dossier.audit_metadata.llm_model}`")
        lines.append(f"- **Contexto (`num_ctx`):** `{dossier.audit_metadata.num_ctx}`")
        lines.append("")
        for reg in dossier.audit_metadata.articles_registry:
            lines.append(
                f"- **{reg.veiculo}** | *{reg.titulo}* | Autor: {reg.autor or 'N/D'} | "
                f"Método: `{reg.metodo_coleta}` | Posição: {reg.posicao_editorial_declarada} | URL: {reg.url_canonica}"
            )
    lines.append("")
    lines.append("---")
    lines.append("*Aviso: A análise é interpretativa e não substitui a leitura das fontes originais.*")
    return "\n".join(lines) + "\n"


@router.get("/{event_id}/dossier", response_model=DossierSchema)
def get_event_dossier(
    event_id: str,
    db: Session = Depends(get_db),
) -> DossierSchema:
    """Retorna todos os dados do dossiê visual com citações verificadas e confiança recalculada."""
    ensure_demo_seed(db)
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evento '{event_id}' não encontrado.",
        )

    dossier = build_verified_dossier_for_event(db, event)
    if dossier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"O evento '{event_id}' ainda não possui dossiê analisado.",
        )
    return dossier


@router.get("/{event_id}/export")
def export_event_dossier(
    event_id: str,
    format: Literal["markdown", "json"] = Query(
        default="json",
        description="Formato de exportação do dossiê: markdown ou json",
    ),
    db: Session = Depends(get_db),
) -> Response:
    """Exporta o Dossiê de Contradição em formato Markdown ou JSON."""
    dossier = get_event_dossier(event_id=event_id, db=db)

    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    if format == "markdown":
        md_content = render_dossier_markdown(dossier)
        try:
            (OUTPUT_DIR / f"dossier_{event_id}.md").write_text(md_content, encoding="utf-8")
        except Exception:
            pass
        return Response(
            content=md_content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="dossier_{event_id}.md"',
            },
        )

    json_content = json.dumps(dossier.model_dump(mode="json"), ensure_ascii=False, indent=2)
    try:
        (OUTPUT_DIR / f"dossier_{event_id}.json").write_text(json_content, encoding="utf-8")
    except Exception:
        pass
    return Response(
        content=json_content,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="dossier_{event_id}.json"',
        },
    )
