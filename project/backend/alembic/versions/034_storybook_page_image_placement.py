"""Storybook page: explicit image_placement enum, drop unused text_box_style.

Revision ID: 034
Revises: 033
Create Date: 2026-08-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "digital_storybook_pages",
        sa.Column("image_placement", sa.String(length=16), server_default="none", nullable=False),
    )
    op.execute(
        "UPDATE digital_storybook_pages SET image_placement='right' WHERE image_url IS NOT NULL"
    )
    op.create_check_constraint(
        "storybook_page_image_placement_allowed",
        "digital_storybook_pages",
        "image_placement IN ('left', 'right', 'above', 'below', 'none')",
    )
    op.drop_column("digital_storybook_pages", "text_box_style")


def downgrade() -> None:
    op.add_column(
        "digital_storybook_pages",
        sa.Column("text_box_style", sa.String(length=32), server_default="card", nullable=False),
    )
    op.drop_constraint(
        "storybook_page_image_placement_allowed", "digital_storybook_pages", type_="check"
    )
    op.drop_column("digital_storybook_pages", "image_placement")
