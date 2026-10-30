"""Add presentation_decks table for Studio and Live modes

Revision ID: 0002_presentation_decks
Revises: 0001_initial
Create Date: 2026-10-30 13:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_presentation_decks"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "presentation_decks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("titulo", sa.String(length=512), nullable=False),
        sa.Column("modo", sa.String(length=32), nullable=False, server_default="ensaio"),
        sa.Column("event_id", sa.String(length=64), nullable=True),
        sa.Column("kpis", sa.JSON(), nullable=False),
        sa.Column("slides", sa.JSON(), nullable=False),
        sa.Column("charts", sa.JSON(), nullable=False),
        sa.Column("ticker_items", sa.JSON(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_presentation_decks_modo", "presentation_decks", ["modo"], unique=False)
    op.create_index("ix_presentation_decks_event_id", "presentation_decks", ["event_id"], unique=False)


def downgrade() -> None:
    op.drop_table("presentation_decks")
