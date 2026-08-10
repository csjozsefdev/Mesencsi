"""users and orders: legal acceptance evidence

Revision ID: 025
Revises: 024
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(conn, table: str) -> set[str]:
    return {c["name"] for c in inspect(conn).get_columns(table)}


def _add_acceptance_columns(table: str) -> None:
    conn = op.get_bind()
    cols = _column_names(conn, table)
    additions = (
        ("terms_accepted_at", sa.DateTime(timezone=True)),
        ("terms_version", sa.String(length=32)),
        ("privacy_acknowledged_at", sa.DateTime(timezone=True)),
        ("privacy_version", sa.String(length=32)),
    )
    for name, column_type in additions:
        if name not in cols:
            op.add_column(table, sa.Column(name, column_type, nullable=True))


def upgrade() -> None:
    _add_acceptance_columns("users")
    _add_acceptance_columns("orders")


def downgrade() -> None:
    for table in ("orders", "users"):
        op.drop_column(table, "privacy_version")
        op.drop_column(table, "privacy_acknowledged_at")
        op.drop_column(table, "terms_version")
        op.drop_column(table, "terms_accepted_at")
