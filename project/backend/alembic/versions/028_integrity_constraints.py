"""Safe CHECK constraints for products, orders, payment_attempts.

Revision ID: 028
Revises: 027
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ORDER_STATUSES = ("new", "processing", "completed", "cancelled")
_PAYMENT_STATUSES = ("pending", "paid", "failed", "cancelled")
_ATTEMPT_STATUSES = ("pending", "paid", "failed", "cancelled")


def _assert_clean(conn, sql: str, label: str) -> None:
    bad = conn.execute(sa.text(sql)).fetchall()
    if bad:
        raise RuntimeError(
            f"Cannot add integrity constraint — {label}. Fix data first. Sample rows: {bad[:5]!r}"
        )


def upgrade() -> None:
    conn = op.get_bind()
    _assert_clean(conn, "SELECT id FROM products WHERE price < 0 LIMIT 5", "products.price < 0")
    _assert_clean(conn, "SELECT id FROM orders WHERE quantity <= 0 LIMIT 5", "orders.quantity <= 0")
    _assert_clean(conn, "SELECT id FROM orders WHERE total_price < 0 LIMIT 5", "orders.total_price < 0")
    _assert_clean(
        conn,
        f"SELECT id FROM orders WHERE payment_status NOT IN {tuple(_PAYMENT_STATUSES)} LIMIT 5",
        "orders.payment_status invalid",
    )
    _assert_clean(
        conn,
        f"SELECT id FROM orders WHERE status NOT IN {tuple(_ORDER_STATUSES)} LIMIT 5",
        "orders.status invalid",
    )
    _assert_clean(
        conn,
        f"SELECT id FROM payment_attempts WHERE status NOT IN {tuple(_ATTEMPT_STATUSES)} LIMIT 5",
        "payment_attempts.status invalid",
    )

    op.create_check_constraint("products_price_non_negative", "products", "price >= 0")
    op.create_check_constraint("orders_quantity_positive", "orders", "quantity > 0")
    op.create_check_constraint("orders_total_price_non_negative", "orders", "total_price >= 0")
    op.create_check_constraint(
        "orders_payment_status_allowed",
        "orders",
        "payment_status IN ('pending', 'paid', 'failed', 'cancelled')",
    )
    op.create_check_constraint(
        "orders_status_allowed",
        "orders",
        "status IN ('new', 'processing', 'completed', 'cancelled')",
    )
    op.create_check_constraint(
        "payment_attempts_status_allowed",
        "payment_attempts",
        "status IN ('pending', 'paid', 'failed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint("payment_attempts_status_allowed", "payment_attempts", type_="check")
    op.drop_constraint("orders_status_allowed", "orders", type_="check")
    op.drop_constraint("orders_payment_status_allowed", "orders", type_="check")
    op.drop_constraint("orders_total_price_non_negative", "orders", type_="check")
    op.drop_constraint("orders_quantity_positive", "orders", type_="check")
    op.drop_constraint("products_price_non_negative", "products", type_="check")
