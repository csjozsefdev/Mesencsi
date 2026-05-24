"""coupons tábla + orders kedvezmény mezők

Revision ID: 010
Revises: 009
Create Date: 2026-05-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("percent_discount", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
    )
    op.create_index("ix_coupons_user_id", "coupons", ["user_id"], unique=False)

    op.add_column("orders", sa.Column("original_total", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("discount_percent", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("discount_amount", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("coupon_code", sa.String(length=64), nullable=True))

    op.execute(
        """
        UPDATE orders
        SET original_total = total_price,
            discount_percent = NULL,
            discount_amount = NULL,
            coupon_code = NULL
        WHERE original_total IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("orders", "coupon_code")
    op.drop_column("orders", "discount_amount")
    op.drop_column("orders", "discount_percent")
    op.drop_column("orders", "original_total")
    op.drop_index("ix_coupons_user_id", table_name="coupons")
    op.drop_table("coupons")
