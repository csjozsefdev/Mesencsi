"""Canonical lowercase emails + token_version for JWT revocation.

Revision ID: 025
Revises: 024
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dupes = conn.execute(
        sa.text(
            "SELECT lower(trim(email)) AS canonical, count(*) AS cnt "
            "FROM users GROUP BY lower(trim(email)) HAVING count(*) > 1"
        )
    ).fetchall()
    if dupes:
        raise RuntimeError(
            "Cannot normalize user emails: duplicate addresses differ only by case/whitespace. "
            f"Resolve manually before migrating: {dupes!r}"
        )
    op.execute(sa.text("UPDATE users SET email = lower(trim(email))"))
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "uq_users_email_lower",
        "users",
        [sa.text("lower(email)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_column("users", "token_version")
