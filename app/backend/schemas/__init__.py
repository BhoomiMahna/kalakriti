"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Auth ────────────────────────────────────────────────────────────────────

class OTPRequest(BaseModel):
    phone: str = Field(..., min_length=8, max_length=20)


class OTPRequestResponse(BaseModel):
    sent: bool
    message: str
    dev_otp: Optional[str] = None       # populated only when OTP_DEV_MODE=true


class OTPVerify(BaseModel):
    phone: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new: bool
    artisan: "ArtisanOut"


# ── Artisan ─────────────────────────────────────────────────────────────────

class ArtisanUpdate(BaseModel):
    name: Optional[str] = None
    preferred_language: Optional[str] = None
    craft_category: Optional[str] = None
    location: Optional[str] = None
    business_name: Optional[str] = None
    gstin: Optional[str] = None


class ArtisanOut(BaseModel):
    id: str
    phone: str
    name: Optional[str]
    preferred_language: str
    craft_category: Optional[str]
    location: Optional[str]
    business_name: Optional[str]
    profile_complete: bool
    ready_to_sell: bool
    profile_completion: int = 0

    class Config:
        from_attributes = True


# ── Products ────────────────────────────────────────────────────────────────

class PriceUpdate(BaseModel):
    price: float = Field(..., gt=0)


class PricingInputs(BaseModel):
    """Inputs the pricing model needs beyond what the AI can infer (spec §10)."""
    category: str
    material: str
    size_bucket: str = "Medium"
    complexity_score: int = Field(3, ge=1, le=5)
    material_cost_inr: float = Field(..., ge=0)
    description: str = ""


class ChannelOut(BaseModel):
    channel: str
    status: str
    external_product_id: Optional[str]
    listing_url: Optional[str]
    error_reason: Optional[str]
    retry_count: int

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: str
    artisan_id: str
    title: Optional[str]
    short_description: Optional[str]
    long_description: Optional[str]
    artisan_story: Optional[str]
    highlights: Optional[list]
    keywords: Optional[list]
    category: Optional[str]
    material: Optional[str]
    dimensions: Optional[str]
    product_facts: Optional[dict]
    original_images: Optional[list]
    enhanced_images: Optional[list]
    generated_images: Optional[dict]
    transcription: Optional[str]
    price: Optional[float]
    suggested_price: Optional[float]
    price_low: Optional[float]
    price_high: Optional[float]
    price_reasoning: Optional[str]
    currency: str
    validation: Optional[dict]
    follow_up_questions: Optional[list]
    status: str
    channels: list[ChannelOut] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: str
    product_id: str
    kind: str
    status: str
    steps: Optional[list]
    error: Optional[str]

    class Config:
        from_attributes = True


class PublishRequest(BaseModel):
    channels: list[str] = Field(default_factory=lambda: ["amazon", "ondc"])


TokenResponse.model_rebuild()
