"""Guest checkout: nullable orders.user_id and guest idempotency table.

Revision ID: 030
Revises: 029
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("orders", "user_id", existing_type=sa.Integer(), nullable=True)

    op.create_table(
        "guest_order_idempotency",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guest_email", sa.String(length=320), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("order_ids_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guest_email", "idempotency_key", name="uq_guest_order_idempotency_email_key"),
    )
    op.create_index("ix_guest_order_idempotency_guest_email", "guest_order_idempotency", ["guest_email"])


def downgrade() -> None:
    op.drop_index("ix_guest_order_idempotency_guest_email", table_name="guest_order_idempotency")
    op.drop_table("guest_order_idempotency")
    op.alter_column("orders", "user_id", existing_type=sa.Integer(), nullable=False)
