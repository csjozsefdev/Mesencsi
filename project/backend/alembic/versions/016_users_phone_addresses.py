"""users: phone, shipping_address, billing_address (profil / checkout előtöltés)

Revision ID: 016
Revises: 015
Create Date: 2026-05-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("shipping_address", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("billing_address", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "billing_address")
    op.drop_column("users", "shipping_address")
    op.drop_column("users", "phone")
