"""Storybook page: add layout_json for the object-canvas editor (V3).

Revision ID: 035
Revises: 034
Create Date: 2026-08-22

Additive, nullable column only. No backfill, no change to any existing
column/constraint/default. Existing pages stay layout_json=NULL until an
admin opens and saves them in the new editor (storybook-reader.js's
legacyPageToLayout() renders NULL pages from the existing legacy fields
in the meantime — see resolvePageLayout()).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "digital_storybook_pages",
        sa.Column("layout_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("digital_storybook_pages", "layout_json")
