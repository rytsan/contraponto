"""Initial schema for Contraponto

Revision ID: 0001_initial
Revises: None
Create Date: 2026-10-28 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=100), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("url_rss", sa.String(length=1024), nullable=False),
        sa.Column("categoria_editorial", sa.String(length=100), nullable=False),
        sa.Column("pais", sa.String(length=16), nullable=False),
        sa.Column("idioma", sa.String(length=16), nullable=False),
        sa.Column("posicao_editorial_declarada", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column("last_modified", sa.String(length=255), nullable=True),
        sa.Column("ultima_coleta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_rss"),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("titulo_provisorio", sa.String(length=512), nullable=False),
        sa.Column("resumo", sa.Text(), nullable=False),
        sa.Column("periodo_inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("periodo_fim", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score_coesao", sa.Float(), nullable=False),
        sa.Column("tema", sa.String(length=64), nullable=False),
        sa.Column("local", sa.String(length=255), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_tema", "events", ["tema"], unique=False)

    op.create_table(
        "articles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column("titulo", sa.String(length=512), nullable=False),
        sa.Column("url_canonica", sa.String(length=1024), nullable=False),
        sa.Column("guid", sa.String(length=1024), nullable=False),
        sa.Column("veiculo", sa.String(length=255), nullable=False),
        sa.Column("autor", sa.String(length=255), nullable=True),
        sa.Column("data_publicacao", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_coleta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("texto_limpo", sa.Text(), nullable=False),
        sa.Column("resumo", sa.Text(), nullable=False),
        sa.Column("idioma", sa.String(length=16), nullable=False),
        sa.Column("hash_conteudo", sa.String(length=128), nullable=False),
        sa.Column("metodo_coleta", sa.String(length=32), nullable=False),
        sa.Column("metadados", sa.JSON(), nullable=False),
        sa.Column("embedding_blob", sa.LargeBinary(), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("entidades_extraidas", sa.JSON(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url_canonica"),
    )
    op.create_index("ix_articles_source_id", "articles", ["source_id"], unique=False)
    op.create_index("ix_articles_event_id", "articles", ["event_id"], unique=False)
    op.create_index("ix_articles_url_canonica", "articles", ["url_canonica"], unique=True)
    op.create_index("ix_articles_guid", "articles", ["guid"], unique=False)
    op.create_index("ix_articles_data_publicacao", "articles", ["data_publicacao"], unique=False)
    op.create_index("ix_articles_hash_conteudo", "articles", ["hash_conteudo"], unique=False)

    op.create_table(
        "article_bias_analyses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("article_id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("verified_ratio", sa.Float(), nullable=False),
        sa.Column("modelo_llm", sa.String(length=255), nullable=False),
        sa.Column("num_ctx", sa.Integer(), nullable=False),
        sa.Column("tempo_execucao_ms", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_article_bias_analyses_article_id", "article_bias_analyses", ["article_id"], unique=False)
    op.create_index("ix_article_bias_analyses_event_id", "article_bias_analyses", ["event_id"], unique=False)

    op.create_table(
        "event_analyses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("dossier_payload", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("modelo_llm", sa.String(length=255), nullable=False),
        sa.Column("num_ctx", sa.Integer(), nullable=False),
        sa.Column("tempo_execucao_ms", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_event_analyses_event_id", "event_analyses", ["event_id"], unique=True)

    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("articles_done", sa.Integer(), nullable=False),
        sa.Column("articles_total", sa.Integer(), nullable=False),
        sa.Column("selected_article_ids", sa.JSON(), nullable=False),
        sa.Column("completed_article_ids", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("modelo_llm", sa.String(length=255), nullable=True),
        sa.Column("num_ctx", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_jobs_event_id", "analysis_jobs", ["event_id"], unique=False)
    op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("analysis_jobs")
    op.drop_table("event_analyses")
    op.drop_table("article_bias_analyses")
    op.drop_table("articles")
    op.drop_table("events")
    op.drop_table("sources")
