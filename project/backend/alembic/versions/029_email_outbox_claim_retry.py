"""email_outbox: claim timestamp, retry backoff, dead-letter status.

Revision ID: 029
Revises: 028
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("email_outbox", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_outbox", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_email_outbox_next_retry_at", "email_outbox", ["next_retry_at"])


def downgrade() -> None:
    op.drop_index("ix_email_outbox_next_retry_at", table_name="email_outbox")
    op.drop_column("email_outbox", "next_retry_at")
    op.drop_column("email_outbox", "claimed_at")
