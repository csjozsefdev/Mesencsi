"""Szűk logikai tesztek a kombó-kedvezmény kiválasztásához és arányos kiosztáshoz (DB nélkül)."""

from __future__ import annotations

from bundle_discount_service import _allocate_bundle_discounts, pick_best_bundle_rule


class _P:
    __slots__ = ("id",)

    def __init__(self, pid: int) -> None:
        self.id = pid


class _Rule:
    __slots__ = ("id", "percent_discount", "products")

    def __init__(self, rid: int, pct: int, ids: list[int]) -> None:
        self.id = rid
        self.percent_discount = pct
        self.products = [_P(i) for i in ids]


def test_allocate_rounding_preserves_total() -> None:
    parts = [100, 100, 100]
    total = 10
    got = _allocate_bundle_discounts(total, parts)
    assert sum(got) == total
    assert got == [3, 3, 4]


def test_pick_best_highest_percent_wins() -> None:
    rules = [_Rule(1, 10, [1, 2]), _Rule(2, 15, [1, 2])]
    cart = {1: 1, 2: 1}
    best = pick_best_bundle_rule(cart, rules)
    assert best is not None
    assert best.id == 2


def test_pick_best_single_product_in_cart_no_combo() -> None:
    rules = [_Rule(1, 50, [1, 2])]
    cart = {1: 5}
    assert pick_best_bundle_rule(cart, rules) is None


def test_pick_best_one_rule_product_only_not_combo() -> None:
    rules = [_Rule(1, 10, [1])]
    cart = {1: 1, 2: 1}
    assert pick_best_bundle_rule(cart, rules) is None
