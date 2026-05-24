"""order payment status + barion / checkout group

Revision ID: 015
Revises: 014
Create Date: 2026-05-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "payment_status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column("orders", sa.Column("barion_payment_id", sa.String(length=128), nullable=True))
    op.add_column("orders", sa.Column("checkout_group_id", sa.String(length=64), nullable=True))
    op.create_index("ix_orders_checkout_group_id", "orders", ["checkout_group_id"], unique=False)
    op.create_index("ix_orders_barion_payment_id", "orders", ["barion_payment_id"], unique=False)

    # Meglévő sorok: előző rendszerben nincs külön fizetés — demo / admin szempontból „kifizetettnek” tekintjük.
    op.execute(sa.text("UPDATE orders SET payment_status = 'paid' WHERE payment_status = 'pending'"))


def downgrade() -> None:
    op.drop_index("ix_orders_barion_payment_id", table_name="orders")
    op.drop_index("ix_orders_checkout_group_id", table_name="orders")
    op.drop_column("orders", "checkout_group_id")
    op.drop_column("orders", "barion_payment_id")
    op.drop_column("orders", "payment_status")
