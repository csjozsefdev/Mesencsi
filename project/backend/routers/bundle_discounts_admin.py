"""Admin: termék-kombó kedvezményszabályok CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from db_models import Product as ProductRow, ProductBundleDiscount
from dependencies import CurrentAdmin, require_role
from models import ProductBundleDiscountCreate, ProductBundleDiscountRead, ProductBundleDiscountUpdate

router = APIRouter(prefix="/bundle-discounts", tags=["admin-bundle-discounts"])


def _product_ids(row: ProductBundleDiscount) -> list[int]:
    return sorted({p.id for p in row.products})


def _to_read(row: ProductBundleDiscount) -> ProductBundleDiscountRead:
    return ProductBundleDiscountRead(
        id=row.id,
        name=row.name,
        description=row.description,
        percent_discount=int(row.percent_discount),
        is_active=bool(row.is_active),
        product_ids=_product_ids(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _get_bundle(db: Session, bundle_id: int) -> ProductBundleDiscount:
    row = db.get(ProductBundleDiscount, bundle_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nincs ilyen kombó kedvezmény.")
    return row


def _load_products(db: Session, ids: list[int]) -> list[ProductRow]:
    rows = list(db.scalars(select(ProductRow).where(ProductRow.id.in_(ids))).all())
    if len(rows) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Egy vagy több megadott termék nem létezik.",
        )
    return rows


@router.get("", response_model=list[ProductBundleDiscountRead])
def admin_list_bundle_discounts(
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["maintenance", "owner"])),
):
    rows = db.scalars(
        select(ProductBundleDiscount)
        .options(selectinload(ProductBundleDiscount.products))
        .order_by(ProductBundleDiscount.id.desc())
    ).all()
    return [_to_read(r) for r in rows]


@router.post("", response_model=ProductBundleDiscountRead, status_code=status.HTTP_201_CREATED)
def admin_create_bundle_discount(
    payload: ProductBundleDiscountCreate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    prows = _load_products(db, list(payload.product_ids))
    row = ProductBundleDiscount(
        name=payload.name.strip(),
        description=payload.description,
        percent_discount=int(payload.percent_discount),
        is_active=payload.is_active,
        products=list(prows),
    )
    db.add(row)
    db.commit()
    row = db.scalar(
        select(ProductBundleDiscount)
        .where(ProductBundleDiscount.id == row.id)
        .options(selectinload(ProductBundleDiscount.products))
    )
    assert row is not None
    return _to_read(row)


@router.patch("/{bundle_id}", response_model=ProductBundleDiscountRead)
def admin_update_bundle_discount(
    bundle_id: int,
    payload: ProductBundleDiscountUpdate,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = _get_bundle(db, bundle_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        row.name = str(data["name"]).strip()
    if "description" in data:
        row.description = data["description"]
    if "percent_discount" in data and data["percent_discount"] is not None:
        row.percent_discount = int(data["percent_discount"])
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = bool(data["is_active"])
    if "product_ids" in data and data["product_ids"] is not None:
        prows = _load_products(db, list(data["product_ids"]))
        row.products = list(prows)
    db.commit()
    row = db.scalar(
        select(ProductBundleDiscount)
        .where(ProductBundleDiscount.id == row.id)
        .options(selectinload(ProductBundleDiscount.products))
    )
    assert row is not None
    return _to_read(row)


@router.delete("/{bundle_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_bundle_discount(
    bundle_id: int,
    db: Session = Depends(get_db),
    _admin: CurrentAdmin = Depends(require_role(["owner"])),
):
    row = _get_bundle(db, bundle_id)
    db.delete(row)
    db.commit()
    return None
