"""gallery_items table for paginated gallery API

Revision ID: 003
Revises: 002
Create Date: 2026-05-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gallery_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gallery_items_sort_order", "gallery_items", ["sort_order"], unique=False)

    gallery = sa.table(
        "gallery_items",
        sa.column("title", sa.String),
        sa.column("image_url", sa.Text),
        sa.column("description", sa.Text),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        gallery,
        [
            {
                "title": "Mesevilág kapuja",
                "image_url": "/images/mesencsi-bg.jpg",
                "description": "Fedezd fel a történetek világát.",
                "sort_order": 0,
            },
            {
                "title": "Esti mese",
                "image_url": "/images/mesencsi-bg.jpg",
                "description": "Nyugodt esték a könyvek mellől.",
                "sort_order": 1,
            },
            {
                "title": "Kaland az olvasásban",
                "image_url": "/images/mesencsi-bg.jpg",
                "description": "Minden oldal új kaland.",
                "sort_order": 2,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_gallery_items_sort_order", table_name="gallery_items")
    op.drop_table("gallery_items")
