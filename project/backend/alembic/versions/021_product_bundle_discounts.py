"""Product bundle (combo) discount rules + orders bundle columns."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "021_product_bundle_discounts"
down_revision = "020_products_image_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_bundle_discounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("percent_discount", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "percent_discount >= 0 AND percent_discount <= 100",
            name="bundle_discount_percent_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "bundle_discount_products",
        sa.Column("bundle_discount_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["bundle_discount_id"], ["product_bundle_discounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("bundle_discount_id", "product_id"),
    )
    op.create_index("ix_bundle_discount_products_product_id", "bundle_discount_products", ["product_id"], unique=False)

    op.add_column("orders", sa.Column("bundle_rule_id", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("bundle_rule_name", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("bundle_discount_amount", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_orders_bundle_rule",
        "orders",
        "product_bundle_discounts",
        ["bundle_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_bundle_rule", "orders", type_="foreignkey")
    op.drop_column("orders", "bundle_discount_amount")
    op.drop_column("orders", "bundle_rule_name")
    op.drop_column("orders", "bundle_rule_id")
    op.drop_index("ix_bundle_discount_products_product_id", table_name="bundle_discount_products")
    op.drop_table("bundle_discount_products")
    op.drop_table("product_bundle_discounts")
