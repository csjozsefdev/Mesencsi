"""payment_attempts — Barion session history per checkout group"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "023_payment_attempts"
down_revision = "022_user_cart_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("checkout_group_id", sa.String(length=64), nullable=False),
        sa.Column("barion_payment_id", sa.String(length=128), nullable=True),
        sa.Column("payment_request_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("barion_payment_id", name="uq_payment_attempts_barion_payment_id"),
        sa.UniqueConstraint("payment_request_id", name="uq_payment_attempts_payment_request_id"),
    )
    op.create_index("ix_payment_attempts_checkout_group_id", "payment_attempts", ["checkout_group_id"])
    op.create_index("ix_payment_attempts_barion_payment_id", "payment_attempts", ["barion_payment_id"])
    # One active attempt per checkout group (concurrent /start guard).
    op.create_index(
        "uq_payment_attempts_active_checkout_group",
        "payment_attempts",
        ["checkout_group_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
        sqlite_where=sa.text("is_active = 1"),
    )


def downgrade() -> None:
    op.drop_index("uq_payment_attempts_active_checkout_group", table_name="payment_attempts")
    op.drop_index("ix_payment_attempts_barion_payment_id", table_name="payment_attempts")
    op.drop_index("ix_payment_attempts_checkout_group_id", table_name="payment_attempts")
    op.drop_table("payment_attempts")
