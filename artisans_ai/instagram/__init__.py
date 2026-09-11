"""
artisan_ai.instagram
=====================

Autonomous Instagram content pipeline: scores products for post-worthiness,
runs content safety checks, generates captions, formats creative, schedules
and publishes to Instagram, then collects engagement feedback to recalibrate
itself over time.

Quick start
-----------
    from artisan_ai.instagram import InstagramContentPipeline, InstagramConfig
    from artisan_ai.instagram.llm_client import LLMClient  # your real client

    config = InstagramConfig(
        ig_access_token="...",
        ig_business_account_id="...",
    )
    pipeline = InstagramContentPipeline(config=config, llm_client=my_llm_client)
    result = pipeline.process(product_output, image_paths=["/path/to/img.jpg"])

See README.md in this package for integration notes -- in particular how to
swap in your real LLM client and merge `InstagramConfig` into your existing
`Config` class.
"""

from .instagram_schema import (
    ImageQualityMetrics,
    PostWorthinessScore,
    InstagramCaption,
    PostLayout,
    LayoutType,
    ScheduledPost,
    PostStatus,
    EngagementMetrics,
    ContentSafetyResult,
)
from .config import InstagramConfig
from .pipeline import InstagramContentPipeline

__all__ = [
    "ImageQualityMetrics",
    "PostWorthinessScore",
    "InstagramCaption",
    "PostLayout",
    "LayoutType",
    "ScheduledPost",
    "PostStatus",
    "EngagementMetrics",
    "ContentSafetyResult",
    "InstagramConfig",
    "InstagramContentPipeline",
]
