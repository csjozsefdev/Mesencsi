"""initial products and orders tables

Revision ID: 001
Revises:
Create Date: 2025-04-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_orders_product_id"), "orders", ["product_id"], unique=False)

    op.bulk_insert(
        sa.table(
            "products",
            sa.column("name", sa.String),
            sa.column("price", sa.Integer),
            sa.column("description", sa.String),
        ),
        [
            {
                "name": "Elso konyv",
                "price": 1000,
                "description": "A high-quality book",
            },
            {
                "name": "Masodik konyv",
                "price": 1500,
                "description": "Another great book",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_product_id"), table_name="orders")
    op.drop_table("orders")
    op.drop_table("products")
