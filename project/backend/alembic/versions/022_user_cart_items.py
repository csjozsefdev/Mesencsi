"""Persist per-user shopping cart items."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "022_user_cart_items"
down_revision = "021_product_bundle_discounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_cart_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_user_cart_user_product"),
    )
    op.create_index("ix_user_cart_items_user_id", "user_cart_items", ["user_id"], unique=False)
    op.create_index("ix_user_cart_items_product_id", "user_cart_items", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_cart_items_product_id", table_name="user_cart_items")
    op.drop_index("ix_user_cart_items_user_id", table_name="user_cart_items")
    op.drop_table("user_cart_items")
