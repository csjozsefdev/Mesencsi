"""Product optional cover image path (local uploads URL)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "020_products_image_url"
down_revision = "019_storybook_page_text_percent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "image_url")
