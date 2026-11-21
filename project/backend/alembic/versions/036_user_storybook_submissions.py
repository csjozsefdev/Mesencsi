"""Nyitási akció: user_storybook_submissions (felhasználói mesekönyv-piszkozatok).

Revision ID: 036
Revises: 035
Create Date: 2026-11-21

Csak új tábla, a meglévő táblákhoz nem nyúl. Idempotens: az alkalmazás a táblát hiányában
maga is létrehozza (storybook_submissions.ensure_submissions_table), ezért itt előbb ellenőrzünk.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "user_storybook_submissions"


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("digital_storybooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("author_name", sa.String(80), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_version", sa.String(32), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_storybook_submissions_book_id", _TABLE, ["book_id"], unique=True)
    op.create_index("ix_user_storybook_submissions_owner_user_id", _TABLE, ["owner_user_id"])
    op.create_index("ix_user_storybook_submissions_status", _TABLE, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(_TABLE):
        op.drop_table(_TABLE)
