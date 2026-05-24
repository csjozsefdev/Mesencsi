"""users.email NOT NULL; orders.user_id FK (kötelező vásárló)

Revision ID: 007
Revises: 006
Create Date: 2026-05-09

Meglévő orders sorok törlődnek (régi vendég checkout); users üres email backfill placeholder.

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE users SET email = username || '@legacy.mesencsi.invalid' "
            "WHERE email IS NULL OR trim(email) = ''"
        )
    )
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=320),
        nullable=False,
    )

    op.add_column("orders", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_orders_user_id_users",
        "orders",
        "users",
        ["user_id"],
        ["id"],
    )
    op.execute(sa.text("DELETE FROM orders"))
    op.alter_column("orders", "user_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.alter_column("orders", "user_id", existing_type=sa.Integer(), nullable=True)
    op.drop_constraint("fk_orders_user_id_users", "orders", type_="foreignkey")
    op.drop_column("orders", "user_id")

    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=320),
        nullable=True,
    )
