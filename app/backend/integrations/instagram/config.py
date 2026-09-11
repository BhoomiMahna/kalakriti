"""
Build the package's InstagramConfig from the platform settings.

Makes `artisans_ai` importable and maps our env-driven settings onto the
standalone dataclass the package expects — without editing the package.
"""
from __future__ import annotations

import sys
from pathlib import Path

from core.config import settings


def _ensure_importable() -> None:
    root = settings.repo_root
    if root not in sys.path:
        sys.path.insert(0, root)


def build_instagram_config():
    """Return an artisans_ai.instagram.InstagramConfig populated from settings."""
    _ensure_importable()
    from artisans_ai.instagram import InstagramConfig  # type: ignore

    feedback_path = settings.instagram_feedback_path or str(
        Path(settings.storage_dir) / "instagram_feedback.jsonl"
    )
    return InstagramConfig(
        gemini_api_key=settings.gemini_api_key or settings.google_api_key,
        ig_access_token=settings.ig_access_token,
        ig_business_account_id=settings.ig_business_account_id,
        ig_account_handle=settings.instagram_account_handle,
        ig_post_threshold=settings.instagram_post_threshold,
        ig_feedback_store_path=feedback_path,
        # Branding stays off until a real logo exists (package default).
        ig_apply_brand_overlay=False,
        ig_brand_logo_path="",
        # Our AI "photoshoot" outputs are clean studio composites (low
        # high-frequency detail by design). The package's default blur
        # thresholds target phone snapshots and misfire on studio shots, so we
        # loosen them here — the separate blank/low-variance check still guards
        # against genuinely empty images.
        ig_blur_threshold_scorer=15.0,
        ig_blur_threshold_safety=20.0,
    )


def has_real_credentials() -> bool:
    return bool(settings.ig_access_token and settings.ig_business_account_id)
