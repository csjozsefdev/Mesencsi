"""orders: shipping_method, shipping_price, shipping_metadata_json.

Revision ID: 031
Revises: 030
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("shipping_method", sa.String(length=32), nullable=True))
    op.add_column(
        "orders",
        sa.Column("shipping_price", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("orders", sa.Column("shipping_metadata_json", sa.JSON(), nullable=True))
    op.create_index("ix_orders_shipping_method", "orders", ["shipping_method"])


def downgrade() -> None:
    op.drop_index("ix_orders_shipping_method", table_name="orders")
    op.drop_column("orders", "shipping_metadata_json")
    op.drop_column("orders", "shipping_price")
    op.drop_column("orders", "shipping_method")
