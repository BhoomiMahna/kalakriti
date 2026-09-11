"""
InstagramProductAdapter — map the platform's canonical Product onto the shape
the standalone Instagram pipeline expects. This is the ONLY place that knows
both shapes; the pipeline stays untouched, and there is no second product store.

Pipeline expects:
    product_output = {
        "product_id": str,
        "category": str,
        "listing": {"description": str, ...},
        "product_facts": {...},
    }
    image_paths = [local file paths]   # scorer/formatter/safety read these with cv2/PIL
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from core.config import settings
from models import Product

STORAGE = Path(settings.storage_dir)


def _media_to_local(url: str | None) -> str | None:
    """/media/<name>  ->  <storage>/<name> if the file exists."""
    if not url:
        return None
    name = Path(url).name
    p = STORAGE / name
    return str(p) if p.exists() else None


def resolve_image_paths(product: Product) -> list[str]:
    """Prefer the AI photoshoot (hero, lifestyle, detail); fall back to originals.

    Returns up to 10 existing local paths (the package caps carousels at 10).
    """
    gen = product.generated_images or {}
    ordered = [gen.get("hero"), gen.get("lifestyle"), gen.get("detail")]
    ordered = [u for u in ordered if u]
    if not ordered:
        ordered = list(product.enhanced_images or product.original_images or [])
    paths = []
    for url in ordered:
        local = _media_to_local(url)
        if local:
            paths.append(local)
    return paths[:10]


def buy_link(product: Product) -> str:
    """A public product link for the caption CTA (marketplace listing if live)."""
    for ch in product.channels or []:
        if ch.status and str(ch.status).endswith("LIVE") and ch.listing_url:
            return f"{settings.api_base_url.rstrip('/')}/#{ch.listing_url}" \
                if ch.listing_url.startswith("/") else ch.listing_url
    return f"{settings.api_base_url.rstrip('/')}/#/product/{product.id}"


def to_product_output(product: Product) -> dict[str, Any]:
    facts = dict(product.product_facts or {})
    facts.setdefault("category", product.category)
    if product.material and "material" not in facts:
        facts["material"] = product.material
    if product.artisan and product.artisan.name:
        facts.setdefault("artisan_name", product.artisan.name)
    if product.artisan and product.artisan.location:
        facts.setdefault("region", product.artisan.location)

    listing = {
        "title": product.title or "",
        "short_description": product.short_description or "",
        "description": product.long_description or product.short_description or "",
        "story": product.artisan_story or "",
        "price": product.price,
        "currency": product.currency,
        "buy_link": buy_link(product),
        "highlights": product.highlights or [],
    }
    return {
        "product_id": product.id,
        "category": product.category or "Handicraft",
        "listing": listing,
        "product_facts": facts,
    }
