from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db_models import DigitalStorybook, DigitalStorybookPage, GalleryItem, NewsPost, Product, ShopOrder, Story


def find_product(session: Session, product_id: int) -> Product:
    row = session.get(Product, product_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen termék.")
    return row


def calculate_total_price(product_price: int, quantity: int) -> int:
    return product_price * quantity


def find_order(session: Session, order_id: int) -> ShopOrder:
    row = session.get(ShopOrder, order_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen rendelés.")
    return row


def find_order_owned(session: Session, order_id: int, user_id: int) -> ShopOrder:
    """Nyilvános /user rendelés: csak a saját user_id tartozó sor látható (404, ha másé vagy nincs)."""
    row = session.get(ShopOrder, order_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="Nincs ilyen rendelés.")
    return row


def find_story(session: Session, story_id: int) -> Story:
    row = session.get(Story, story_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen mese.")
    return row


def find_gallery_row(session: Session, item_id: int) -> GalleryItem:
    row = session.get(GalleryItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen galériakép.")
    return row


def find_news_post(session: Session, news_id: int) -> NewsPost:
    row = session.get(NewsPost, news_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen hír.")
    return row


def require_published_news_post(session: Session, news_id: int) -> NewsPost:
    """Publikus hírkommentek: csak közzétett hírhez engedünk listázást / írást."""
    row = session.get(NewsPost, news_id)
    if row is None or not row.is_published:
        raise HTTPException(status_code=404, detail="Nincs ilyen közzétett hír.")
    return row


def find_digital_storybook(session: Session, book_id: int) -> DigitalStorybook:
    row = session.get(DigitalStorybook, book_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Nincs ilyen mesekönyv.")
    return row


def require_published_storybook_by_slug(session: Session, slug: str) -> DigitalStorybook:
    """Publikus olvasó: csak közzétett könyv."""
    row = session.scalar(select(DigitalStorybook).where(DigitalStorybook.slug == slug.strip()))
    if row is None or not row.is_published:
        raise HTTPException(status_code=404, detail="Nincs ilyen közzétett mesekönyv.")
    return row


def find_storybook_page_for_book(session: Session, book_id: int, page_id: int) -> DigitalStorybookPage:
    row = session.get(DigitalStorybookPage, page_id)
    if row is None or row.book_id != book_id:
        raise HTTPException(status_code=404, detail="Nincs ilyen oldal ebben a könyvben.")
    return row
