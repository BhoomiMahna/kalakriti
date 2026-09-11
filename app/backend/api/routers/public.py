"""
Public (no-auth) endpoints for the demo marketplace listing pages.

A judge opening /demo/amazon/product/ART-48291 needs the product data without
logging in. This resolves a marketplace listing id to its canonical product.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_db
from models import Product, ProductChannel

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/listing/{external_id}")
def get_listing(external_id: str, db: Session = Depends(get_db)) -> dict:
    channel = (
        db.query(ProductChannel)
        .filter(ProductChannel.external_product_id == external_id)
        .first()
    )
    if not channel:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
    product: Product = channel.product
    artisan = product.artisan
    gen = product.generated_images or {}
    images = [gen.get("hero"), gen.get("lifestyle"), gen.get("detail")]
    images = [i for i in images if i] or product.enhanced_images or product.original_images or []
    return {
        "external_id": external_id,
        "channel": channel.channel,
        "is_demo": (channel.listing_url or "").startswith("/demo/"),
        "title": product.title,
        "short_description": product.short_description,
        "long_description": product.long_description,
        "artisan_story": product.artisan_story,
        "highlights": product.highlights or [],
        "price": product.price,
        "currency": product.currency,
        "category": product.category,
        "material": product.material,
        "dimensions": product.dimensions,
        "images": images,
        "artisan_name": artisan.name if artisan else None,
        "artisan_location": artisan.location if artisan else None,
    }
