"""order checkout: customer, shipping, status, placed_at

Revision ID: 004
Revises: 003
Create Date: 2026-05-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("customer_name", sa.String(length=255), server_default="Vásárló", nullable=False),
    )
    op.add_column("orders", sa.Column("customer_email", sa.String(length=320), nullable=True))
    op.add_column("orders", sa.Column("shipping_address", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "orders",
        sa.Column("status", sa.String(length=32), server_default="new", nullable=False),
    )
    op.add_column(
        "orders",
        sa.Column(
            "placed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.alter_column("orders", "customer_name", server_default=None)


def downgrade() -> None:
    op.drop_column("orders", "placed_at")
    op.drop_column("orders", "status")
    op.drop_column("orders", "notes")
    op.drop_column("orders", "shipping_address")
    op.drop_column("orders", "customer_email")
    op.drop_column("orders", "customer_name")
