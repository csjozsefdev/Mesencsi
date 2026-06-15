"""Termék-kombó (bundle) kedvezmény: szabályok illesztése és checkout árazás."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from coupon_service import line_amounts_with_discount, resolve_usable_coupon
from db_models import ProductBundleDiscount
from fastapi import HTTPException, status
from services import calculate_total_price, find_product

# Legalább két különböző termék kell — egyféle termék több darabja nem „kombó”.
MIN_BUNDLE_DISTINCT_PRODUCTS = 2


@dataclass(frozen=True)
class PricedCartLine:
    product_id: int
    product_name: str
    quantity: int
    original_total: int
    discount_amount: int
    final_total: int
    discount_percent: int | None
    coupon_code: str | None
    bundle_rule_id: int | None
    bundle_rule_name: str | None
    bundle_discount_amount: int | None


@dataclass(frozen=True)
class CheckoutPricingResult:
    lines: list[PricedCartLine]
    grand_original: int
    grand_discount: int
    grand_final: int
    coupon_code: str | None
    discount_percent: int | None
    bundle_rule_id: int | None
    bundle_rule_name: str | None
    bundle_discount_total: int
    bundle_percent: int | None


def _cart_quantities(items: Sequence[object]) -> dict[int, int]:
    q: dict[int, int] = {}
    for it in items:
        pid = int(getattr(it, "product_id"))
        n = int(getattr(it, "quantity"))
        q[pid] = q.get(pid, 0) + n
    return q


def _load_active_bundle_rules(db: Session) -> list[ProductBundleDiscount]:
    return list(
        db.scalars(
            select(ProductBundleDiscount)
            .where(ProductBundleDiscount.is_active.is_(True))
            .options(selectinload(ProductBundleDiscount.products))
            .order_by(ProductBundleDiscount.id.asc())
        ).all()
    )


def pick_best_bundle_rule(cart_qty: dict[int, int], rules: Sequence[ProductBundleDiscount]) -> ProductBundleDiscount | None:
    candidates: list[ProductBundleDiscount] = []
    for rule in rules:
        ids = {p.id for p in rule.products}
        if len(ids) < MIN_BUNDLE_DISTINCT_PRODUCTS:
            continue
        if all(cart_qty.get(pid, 0) >= 1 for pid in ids):
            candidates.append(rule)
    if not candidates:
        return None
    return max(candidates, key=lambda r: (int(r.percent_discount), r.id))


def _allocate_bundle_discounts(total_discount: int, originals: list[int]) -> list[int]:
    """Arányos egész Ft kedvezmény — az utolsó sor kapja a kerekítési maradékot."""
    n = len(originals)
    if n == 0:
        return []
    base = sum(originals)
    if base <= 0 or total_discount <= 0:
        return [0] * n
    out: list[int] = []
    remaining = total_discount
    for orig in originals[:-1]:
        d = (total_discount * orig) // base
        out.append(d)
        remaining -= d
    out.append(remaining)
    return out


def compute_checkout_pricing(
    db: Session,
    *,
    user_id: int | None,
    items: Sequence[object],
    coupon_code: str | None,
) -> CheckoutPricingResult:
    """Kosár árazás: aktív kombó szabály elsőbbsége a kuponnal szemben; a szerver számol mindent."""
    rules = _load_active_bundle_rules(db)
    cart_qty = _cart_quantities(items)
    best = pick_best_bundle_rule(cart_qty, rules)

    # Soronkénti eredeti összegek (a kérés sorrendjében)
    row_originals: list[int] = []
    row_metas: list[tuple[int, str, int]] = []  # product_id, name, quantity
    for it in items:
        p = find_product(db, int(getattr(it, "product_id")))
        qty = int(getattr(it, "quantity"))
        orig = calculate_total_price(p.price, qty)
        row_originals.append(orig)
        row_metas.append((p.id, p.name, qty))

    grand_o = sum(row_originals)

    if best is not None:
        rule_ids = {p.id for p in best.products}
        base = sum(orig for orig, (pid, _, _) in zip(row_originals, row_metas) if pid in rule_ids)
        pct = int(best.percent_discount)
        pct = max(0, min(100, pct))
        total_bundle_discount = (base * pct) // 100

        bundle_indices = [i for i, (pid, _, _) in enumerate(row_metas) if pid in rule_ids]
        bundle_originals = [row_originals[i] for i in bundle_indices]
        parts = _allocate_bundle_discounts(total_bundle_discount, bundle_originals)
        idx_to_bundle_disc = dict(zip(bundle_indices, parts))

        lines: list[PricedCartLine] = []
        for i, (orig, (pid, name, qty)) in enumerate(zip(row_originals, row_metas)):
            bd = idx_to_bundle_disc.get(i, 0)
            final = orig - bd
            in_bundle = pid in rule_ids
            lines.append(
                PricedCartLine(
                    product_id=pid,
                    product_name=name,
                    quantity=qty,
                    original_total=orig,
                    discount_amount=bd,
                    final_total=final,
                    discount_percent=pct if in_bundle else None,
                    coupon_code=None,
                    bundle_rule_id=best.id if in_bundle else None,
                    bundle_rule_name=best.name if in_bundle else None,
                    bundle_discount_amount=bd if in_bundle else None,
                )
            )
        g_d = sum(pl.discount_amount for pl in lines)
        g_f = sum(pl.final_total for pl in lines)
        return CheckoutPricingResult(
            lines=lines,
            grand_original=grand_o,
            grand_discount=g_d,
            grand_final=g_f,
            coupon_code=None,
            discount_percent=None,
            bundle_rule_id=best.id,
            bundle_rule_name=best.name,
            bundle_discount_total=total_bundle_discount,
            bundle_percent=pct,
        )

    pct: int | None = None
    code_display: str | None = None
    if coupon_code:
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A kuponok csak bejelentkezett, e-mailben megerősített fiókkal használhatók.",
            )
        c = resolve_usable_coupon(db, code=coupon_code, user_id=user_id)
        pct = int(c.percent_discount)
        code_display = c.code

    lines2: list[PricedCartLine] = []
    g_d = 0
    g_f = 0
    for orig, (pid, name, qty) in zip(row_originals, row_metas):
        if pct is not None:
            da, final, _p = line_amounts_with_discount(orig, pct)
        else:
            da, final, _p = 0, orig, None
        lines2.append(
            PricedCartLine(
                product_id=pid,
                product_name=name,
                quantity=qty,
                original_total=orig,
                discount_amount=da,
                final_total=final,
                discount_percent=pct,
                coupon_code=code_display,
                bundle_rule_id=None,
                bundle_rule_name=None,
                bundle_discount_amount=None,
            )
        )
        g_d += da
        g_f += final

    return CheckoutPricingResult(
        lines=lines2,
        grand_original=grand_o,
        grand_discount=g_d,
        grand_final=g_f,
        coupon_code=code_display,
        discount_percent=pct,
        bundle_rule_id=None,
        bundle_rule_name=None,
        bundle_discount_total=0,
        bundle_percent=None,
    )
