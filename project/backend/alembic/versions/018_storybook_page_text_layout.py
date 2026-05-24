"""storybook pages: text position + box style columns

Revision ID: 018
Revises: 017
Create Date: 2026-05-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "digital_storybook_pages",
        sa.Column(
            "text_position_vertical",
            sa.String(length=16),
            server_default="center",
            nullable=False,
        ),
    )
    op.add_column(
        "digital_storybook_pages",
        sa.Column(
            "text_position_horizontal",
            sa.String(length=16),
            server_default="center",
            nullable=False,
        ),
    )
    op.add_column(
        "digital_storybook_pages",
        sa.Column(
            "text_box_style",
            sa.String(length=32),
            server_default="card",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("digital_storybook_pages", "text_box_style")
    op.drop_column("digital_storybook_pages", "text_position_horizontal")
    op.drop_column("digital_storybook_pages", "text_position_vertical")
