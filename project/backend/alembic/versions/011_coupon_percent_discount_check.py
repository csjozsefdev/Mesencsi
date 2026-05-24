"""coupons.percent_discount CHECK 1..100

Revision ID: 011
Revises: 010
Create Date: 2026-05-10

"""

from typing import Sequence, Union

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "coupons_percent_discount_range",
        "coupons",
        "percent_discount >= 1 AND percent_discount <= 100",
    )


def downgrade() -> None:
    op.drop_constraint("coupons_percent_discount_range", "coupons", type_="check")
