"""Storybook page: optional custom text box position (percent of canvas).

Revision ID: 019
Revises: 018
Create Date: 2026-05-10

text_x_percent / text_y_percent: anchor point of the text box (typically center)
as percentage of the page inner area (0–100). NULL = use text_position_* alignment.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019_storybook_page_text_percent"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "digital_storybook_pages",
        sa.Column("text_x_percent", sa.Float(), nullable=True),
    )
    op.add_column(
        "digital_storybook_pages",
        sa.Column("text_y_percent", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("digital_storybook_pages", "text_y_percent")
    op.drop_column("digital_storybook_pages", "text_x_percent")
