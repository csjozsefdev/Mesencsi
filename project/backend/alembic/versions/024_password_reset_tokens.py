"""users: password reset token hash + timestamps

Revision ID: 024
Revises: 023_payment_attempts
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "024"
down_revision: Union[str, None] = "023_payment_attempts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _users_column_names(conn) -> set[str]:
    return {c["name"] for c in inspect(conn).get_columns("users")}


def _users_index_names(conn) -> set[str]:
    return {i["name"] for i in inspect(conn).get_indexes("users")}


def upgrade() -> None:
    conn = op.get_bind()
    cols = _users_column_names(conn)
    if "password_reset_token_hash" not in cols:
        op.add_column("users", sa.Column("password_reset_token_hash", sa.String(length=64), nullable=True))
    if "password_reset_sent_at" not in cols:
        op.add_column("users", sa.Column("password_reset_sent_at", sa.DateTime(timezone=True), nullable=True))
    if "password_reset_used_at" not in cols:
        op.add_column("users", sa.Column("password_reset_used_at", sa.DateTime(timezone=True), nullable=True))
    if "ix_users_password_reset_token_hash" not in _users_index_names(conn):
        op.create_index(
            "ix_users_password_reset_token_hash",
            "users",
            ["password_reset_token_hash"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_users_password_reset_token_hash", table_name="users")
    op.drop_column("users", "password_reset_used_at")
    op.drop_column("users", "password_reset_sent_at")
    op.drop_column("users", "password_reset_token_hash")
