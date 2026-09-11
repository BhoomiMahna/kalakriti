"""
Database models.

The design keeps the *canonical product* decoupled from any marketplace:
Product is the single source of truth, and ProductChannel rows hold the
per-marketplace publishing state — so adding a channel never touches the
product pipeline (spec §11, §21, §26).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.session import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ───────────────────────────────────────────────────────────────────

class ProductStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    AI_PROCESSING = "AI_PROCESSING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    PUBLISHING = "PUBLISHING"
    LIVE = "LIVE"
    FAILED = "FAILED"


class ChannelStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    LIVE = "LIVE"
    FAILED = "FAILED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


# ── Artisan ─────────────────────────────────────────────────────────────────

class Artisan(Base):
    __tablename__ = "artisans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    craft_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)

    # Seller / business info (kept once — artisan registers once, spec §4.1)
    business_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_account_last4: Mapped[str | None] = mapped_column(String(8), nullable=True)

    profile_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    ready_to_sell: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    products: Mapped[list["Product"]] = relationship(back_populates="artisan", cascade="all, delete-orphan")

    def completion_pct(self) -> int:
        fields = [self.name, self.preferred_language, self.craft_category,
                  self.location, self.business_name]
        filled = sum(1 for f in fields if f)
        return round(100 * filled / len(fields))


# ── OTP ─────────────────────────────────────────────────────────────────────

class OTP(Base):
    __tablename__ = "otps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ── Product (canonical source of truth) ─────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    artisan_id: Mapped[str] = mapped_column(ForeignKey("artisans.id"), index=True)

    # Generated listing content
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    long_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    artisan_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    highlights: Mapped[list | None] = mapped_column(JSON, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Facts / metadata
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    material: Mapped[str | None] = mapped_column(String(160), nullable=True)
    dimensions: Mapped[str | None] = mapped_column(String(120), nullable=True)
    product_facts: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Media
    original_images: Mapped[list | None] = mapped_column(JSON, nullable=True)
    enhanced_images: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # AI photoshoot output: {"hero": url, "lifestyle": url, "detail": url, "mode": str}
    generated_images: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    voice_recording: Mapped[str | None] = mapped_column(String(300), nullable=True)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pricing
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    # Pipeline artifacts
    ai_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    follow_up_questions: Mapped[list | None] = mapped_column(JSON, nullable=True)

    status: Mapped[ProductStatus] = mapped_column(Enum(ProductStatus), default=ProductStatus.DRAFT)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    artisan: Mapped["Artisan"] = relationship(back_populates="products")
    channels: Mapped[list["ProductChannel"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


# ── Per-marketplace channel state ───────────────────────────────────────────

class ProductChannel(Base):
    __tablename__ = "product_channels"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    channel: Mapped[str] = mapped_column(String(40))          # "amazon" | "ondc" | ...
    status: Mapped[ChannelStatus] = mapped_column(Enum(ChannelStatus), default=ChannelStatus.PENDING)
    external_product_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    listing_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    product: Mapped["Product"] = relationship(back_populates="channels")


# ── Instagram automation posts (platform-level, single brand account) ───────

class InstagramPostStatus(str, enum.Enum):
    EVALUATING = "EVALUATING"
    HELD_BACK = "HELD_BACK"        # score below threshold
    UNSAFE = "UNSAFE"             # failed safety checks
    SCHEDULED = "SCHEDULED"        # passed, awaiting publish (real mode, no immediate publish)
    DEMO_PUBLISHED = "DEMO_PUBLISHED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class InstagramPost(Base):
    """One Instagram automation attempt for a canonical product.

    References the product (no product-data duplication). Holds the pipeline's
    decision + generated content for the admin view and demo preview.
    """
    __tablename__ = "instagram_posts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    status: Mapped[InstagramPostStatus] = mapped_column(
        Enum(InstagramPostStatus), default=InstagramPostStatus.EVALUATING
    )
    demo: Mapped[bool] = mapped_column(Boolean, default=True)

    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    safety_safe: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    safety_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    caption_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    call_to_action: Mapped[str | None] = mapped_column(String(300), nullable=True)
    layout_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    image_urls: Mapped[list | None] = mapped_column(JSON, nullable=True)

    scheduled_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    instagram_post_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    permalink: Mapped[str | None] = mapped_column(String(400), nullable=True)
    engagement: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    product: Mapped["Product"] = relationship()


# ── Async job records (orchestration + retryability) ────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))             # "ai_pipeline" | "publish"
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED)
    # Per-step progress the frontend polls (spec §19 progress list)
    steps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    product: Mapped["Product"] = relationship(back_populates="jobs")
