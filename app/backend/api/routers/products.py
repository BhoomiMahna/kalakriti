"""Product creation, the automated pipeline, review, and publishing."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from api.deps import get_current_artisan
from core.config import settings
from db.session import get_db
from models import (
    Artisan,
    ChannelStatus,
    Job,
    Product,
    ProductChannel,
    ProductStatus,
)
from schemas import (
    JobOut,
    PriceUpdate,
    PricingInputs,
    ProductOut,
    PublishRequest,
)
from services import job_service
from services.pricing_service import get_pricing_service

router = APIRouter(tags=["products"])

STORAGE = Path(settings.storage_dir)
STORAGE.mkdir(parents=True, exist_ok=True)
ALLOWED_IMG = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
ALLOWED_AUDIO = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}


def _save_upload(upload: UploadFile, allowed: set[str]) -> str:
    ext = Path(upload.filename or "").suffix.lower() or ".bin"
    if ext not in allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported file type: {ext}")
    name = f"{uuid.uuid4().hex}{ext}"
    dest = STORAGE / name
    with dest.open("wb") as fh:
        fh.write(upload.file.read())
    return name


# ── Pricing helpers (guided questions, spec §10) ─────────────────────────────

@router.get("/pricing/metadata")
def pricing_metadata() -> dict:
    return get_pricing_service().metadata()


@router.post("/pricing/suggest")
def pricing_suggest(payload: PricingInputs) -> dict:
    return get_pricing_service().suggest(
        category=payload.category,
        material=payload.material,
        size_bucket=payload.size_bucket,
        complexity_score=payload.complexity_score,
        material_cost_inr=payload.material_cost_inr,
        description=payload.description,
    )


# ── Product lifecycle ────────────────────────────────────────────────────────

@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    images: list[UploadFile] = File(default=[]),
    audio: UploadFile | None = File(default=None),
    product_name: str = Form(""),
    category: str = Form(""),
    material: str = Form(""),
    dimensions: str = Form(""),
    text_hint: str = Form(""),           # confirmed transcript (spoken language) or typed text
    language: str = Form(""),            # spoken/selected language (en|hi|pa|...)
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> ProductOut:
    """Create a draft product from photos + voice/text, then kick off the
    automated AI pipeline asynchronously (spec §5, §19)."""
    if not images and not text_hint and not audio:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Provide at least one photo, a voice recording, or text.")

    original = [f"/media/{_save_upload(img, ALLOWED_IMG)}" for img in images if img.filename]
    audio_name = _save_upload(audio, ALLOWED_AUDIO) if audio and audio.filename else None

    product = Product(
        artisan_id=artisan.id,
        category=category or artisan.craft_category,
        material=material or None,
        dimensions=dimensions or None,
        original_images=original or None,
        voice_recording=f"/media/{audio_name}" if audio_name else None,
        status=ProductStatus.DRAFT,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    lang = language or artisan.preferred_language or "en"
    # If the audio was NOT already transcribed on the client review step,
    # allow the pipeline to transcribe it; otherwise text_hint is authoritative.
    job_service.start_ai_pipeline(product.id, inputs={
        "audio_path": str(STORAGE / audio_name) if (audio_name and not text_hint) else None,
        "confirmed_transcript": text_hint,   # already in spoken language, confirmed
        "text_hint": text_hint,
        "product_name": product_name,
        "category": category or (artisan.craft_category or ""),
        "material": material,
        "dimensions": dimensions,
        "artisan_name": artisan.name or "",
        "region": artisan.location or "",
        "language": lang,
    })
    db.refresh(product)
    return ProductOut.model_validate(product)


@router.get("/products", response_model=list[ProductOut])
def list_products(
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> list[ProductOut]:
    products = (
        db.query(Product)
        .filter(Product.artisan_id == artisan.id)
        .order_by(Product.created_at.desc())
        .all()
    )
    return [ProductOut.model_validate(p) for p in products]


def _owned_product(product_id: str, artisan: Artisan, db: Session) -> Product:
    product = db.get(Product, product_id)
    if not product or product.artisan_id != artisan.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(
    product_id: str,
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> ProductOut:
    return ProductOut.model_validate(_owned_product(product_id, artisan, db))


@router.get("/products/{product_id}/job", response_model=JobOut | None)
def latest_job(
    product_id: str,
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> Job | None:
    _owned_product(product_id, artisan, db)
    return (
        db.query(Job)
        .filter(Job.product_id == product_id)
        .order_by(Job.created_at.desc())
        .first()
    )


@router.post("/products/{product_id}/photoshoot", response_model=ProductOut)
def regenerate_photoshoot(
    product_id: str,
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> ProductOut:
    """Re-run the AI product photoshoot (manual retry). Blocks until done."""
    product = _owned_product(product_id, artisan, db)
    job_service.regenerate_photoshoot(product_id)
    db.expire(product)
    return ProductOut.model_validate(db.get(Product, product_id))


@router.patch("/products/{product_id}/price", response_model=ProductOut)
def set_price(
    product_id: str,
    payload: PriceUpdate,
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> ProductOut:
    product = _owned_product(product_id, artisan, db)
    product.price = payload.price
    db.commit()
    db.refresh(product)
    return ProductOut.model_validate(product)


@router.post("/products/{product_id}/approve", response_model=ProductOut)
def approve_product(
    product_id: str,
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> ProductOut:
    product = _owned_product(product_id, artisan, db)
    if product.status not in (ProductStatus.READY_FOR_REVIEW, ProductStatus.APPROVED,
                              ProductStatus.LIVE):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Product is not ready for review (status: {product.status.value}).")
    product.status = ProductStatus.APPROVED
    db.commit()
    db.refresh(product)
    return ProductOut.model_validate(product)


@router.post("/products/{product_id}/publish", response_model=JobOut)
def publish_product(
    product_id: str,
    payload: PublishRequest,
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> Job:
    product = _owned_product(product_id, artisan, db)
    if not product.title or product.price is None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Product must have a title and price before publishing.")
    job = job_service.start_publish(product_id, payload.channels)
    return job


@router.post("/products/{product_id}/channels/{channel}/retry", response_model=JobOut)
def retry_channel(
    product_id: str,
    channel: str,
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> Job:
    product = _owned_product(product_id, artisan, db)
    row = (db.query(ProductChannel)
             .filter_by(product_id=product_id, channel=channel).first())
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel not found for product")
    row.status = ChannelStatus.PENDING
    db.commit()
    return job_service.start_publish(product_id, [channel])
