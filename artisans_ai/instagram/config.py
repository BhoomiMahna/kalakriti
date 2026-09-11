"""
Instagram pipeline configuration.

Standalone for now (per your existing `artisan_ai.config.Config` not being
available here). Field names match the spec exactly so you can lift them
into your real `Config` class later -- see MERGE NOTES at the bottom.

Defaults reflect what you confirmed:
  - no brand logo/overlay (ig_brand_logo_path="" disables the overlay)
  - single brand account (no per-artisan account mapping)
  - 3 hour minimum gap between auto-posts
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InstagramConfig:
  # Gemini credentials/model. If the key is empty, GeminiLLMClient reads
  # GEMINI_API_KEY from the environment.
    gemini_api_key: str = ""  
    gemini_model: str = "gemini-2.5-flash"

    # Instagram Graph API credentials (required before AutoScheduler/Publisher
    # can actually publish -- see README "Credentials" section)
    ig_access_token: str = ""
    ig_business_account_id: str = ""

    # Posting behaviour
    ig_post_threshold: float = 0.85      # min post-worthiness score to auto-publish
    ig_requeue_days: int = 7             # re-score held-back posts after N days
    ig_min_post_gap_hours: int = 3       # confirmed: 3 hours between auto-posts
    ig_threshold_floor: float = 0.65     # feedback loop won't relax below this

    # Branding -- disabled per your confirmation (no logo / no overlay).
    # Leave ig_brand_logo_path empty to skip the overlay entirely.
    ig_brand_logo_path: str = ""
    ig_brand_color: str = "#D4A373"
    ig_apply_brand_overlay: bool = False

    # Single brand account -- no per-artisan account routing.
    ig_account_handle: str = "@kaia_kriti"

    # Storage
    ig_feedback_store_path: str = "instagram_feedback.jsonl"

    # Scoring weights
    ig_scorer_weights: dict = field(
        default_factory=lambda: {"image": 0.30, "story": 0.45, "category": 0.25}
    )

    # Engagement polling (not explicitly confirmed -- defaulting to every 6h;
    # tune freely, this only affects how often collect_feedback() should be
    # invoked by your scheduler/cron, the pipeline itself doesn't self-poll)
    ig_engagement_poll_hours: int = 6

    # Image quality thresholds
    ig_min_resolution_px: int = 1080
    ig_blur_threshold_scorer: float = 100.0   # Laplacian variance, lenient
    ig_blur_threshold_safety: float = 150.0   # stricter re-check before publish


# ── MERGE NOTES ──────────────────────────────────────────────────────────
# To fold this into your existing artisan_ai/config.py `Config` class,
# copy the fields above into it directly (flat, no nesting) -- every
# consumer in this package (`scorer.py`, `scheduler.py`, etc.) only reads
# attributes by name, so any object with these attributes works, dataclass
# or not.
