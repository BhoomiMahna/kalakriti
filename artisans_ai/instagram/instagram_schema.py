"""Pydantic data models for the Instagram content pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────────────────
# Image quality
# ────────────────────────────────────────────────────────────────────────────

class ImageQualityMetrics(BaseModel):
    """Raw + derived image quality signals for a single image."""

    image_path: str
    blur_score: float = Field(..., description="Laplacian variance; higher = sharper")
    width: int
    height: int
    aspect_ratio: float
    is_blurry: bool
    meets_min_resolution: bool
    aspect_ratio_valid: bool
    composition_score: float = Field(0.5, ge=0.0, le=1.0)
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Normalized 0-1 composite")


# ────────────────────────────────────────────────────────────────────────────
# Post-worthiness
# ────────────────────────────────────────────────────────────────────────────

class PostWorthinessScore(BaseModel):
    """Composite score deciding whether a product is worth auto-posting."""

    product_id: str
    image_score: float = Field(..., ge=0.0, le=1.0)
    story_score: float = Field(..., ge=0.0, le=1.0)
    category_score: float = Field(..., ge=0.0, le=1.0)
    composite_score: float = Field(..., ge=0.0, le=1.0)
    weights_used: dict = Field(default_factory=dict)
    is_cold_start_category: bool = False
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    notes: list[str] = Field(default_factory=list)


# ────────────────────────────────────────────────────────────────────────────
# Caption
# ────────────────────────────────────────────────────────────────────────────

class InstagramCaption(BaseModel):
    caption_text: str
    hashtags: list[str] = Field(default_factory=list)
    call_to_action: str
    character_count: int

    @property
    def full_text(self) -> str:
        """Caption + hashtags formatted the way Instagram expects it."""
        tags = " ".join(f"#{t.lstrip('#')}" for t in self.hashtags)
        return f"{self.caption_text}\n\n{self.call_to_action}\n\n{tags}".strip()


# ────────────────────────────────────────────────────────────────────────────
# Layout / creative
# ────────────────────────────────────────────────────────────────────────────

class LayoutType(str, Enum):
    SINGLE_IMAGE = "single_image"
    CAROUSEL = "carousel"
    REEL_COVER = "reel_cover"


class PostLayout(BaseModel):
    layout_type: LayoutType
    media_paths: list[str]
    brand_overlay_applied: bool = False


# ────────────────────────────────────────────────────────────────────────────
# Scheduling
# ────────────────────────────────────────────────────────────────────────────

class PostStatus(str, Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    HELD_BACK = "held_back"
    FAILED = "failed"


class ScheduledPost(BaseModel):
    product_id: str
    caption: Optional[InstagramCaption] = None
    layout: Optional[PostLayout] = None
    worthiness_score: Optional[PostWorthinessScore] = None
    safety_result: Optional[ContentSafetyResult] = None  # forward ref, defined below
    scheduled_publish_time: Optional[datetime] = None
    status: PostStatus = PostStatus.PENDING
    instagram_post_id: Optional[str] = None
    requeue_after: Optional[datetime] = None
    error: Optional[str] = None


# ────────────────────────────────────────────────────────────────────────────
# Engagement
# ────────────────────────────────────────────────────────────────────────────

class EngagementMetrics(BaseModel):
    instagram_post_id: str
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    reach: int = 0
    impressions: int = 0
    collected_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def engagement_rate(self) -> float:
        if self.reach <= 0:
            return 0.0
        return (self.likes + self.comments + self.shares + self.saves) / self.reach


# ────────────────────────────────────────────────────────────────────────────
# Safety
# ────────────────────────────────────────────────────────────────────────────

class ContentSafetyResult(BaseModel):
    safe: bool
    flags: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)


# Resolve forward reference used in ScheduledPost
ScheduledPost.model_rebuild()
