"""Storybook page: optional custom image position and size (percent of canvas).

Revision ID: 032
Revises: 031
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "digital_storybook_pages",
        sa.Column("image_x_percent", sa.Float(), nullable=True),
    )
    op.add_column(
        "digital_storybook_pages",
        sa.Column("image_y_percent", sa.Float(), nullable=True),
    )
    op.add_column(
        "digital_storybook_pages",
        sa.Column("image_width_percent", sa.Float(), nullable=True),
    )
    op.add_column(
        "digital_storybook_pages",
        sa.Column("image_height_percent", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("digital_storybook_pages", "image_height_percent")
    op.drop_column("digital_storybook_pages", "image_width_percent")
    op.drop_column("digital_storybook_pages", "image_y_percent")
    op.drop_column("digital_storybook_pages", "image_x_percent")
