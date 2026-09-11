"""
Smoke tests for the Instagram content pipeline.

These use a FakeLLM and synthetic images so they run with no network access
and no real credentials. Run with: pytest tests/test_instagram/
"""

import os

import cv2
import numpy as np
import pytest

from artisans_ai.instagram.config import InstagramConfig
from artisans_ai.instagram.feedback_store import FeedbackStore
from artisans_ai.instagram.formatter import CreativeFormatter
from artisans_ai.instagram.instagram_schema import LayoutType, PostStatus
from artisans_ai.instagram.pipeline import InstagramContentPipeline
from artisans_ai.instagram.scorer import ImageQualityAnalyzer


class FakeLLM:
    """Deterministic fake LLM covering every prompt this package sends."""

    def __init__(self, uniqueness: str = "8", coherent: str = "YES"):
        self.uniqueness = uniqueness
        self.coherent = coherent

    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        if "Uniqueness rating" in user_prompt:
            return self.uniqueness
        if "Consistent?" in user_prompt:
            return self.coherent
        return (
            '{"caption_text": "A handcrafted piece with a story.", '
            '"hashtags": ["handmade","craft","artisan","pottery","decor",'
            '"homedecor","supportlocal","ceramics","clayart","boho",'
            '"art","gift","heritage","madewithlove","unique"], '
            '"call_to_action": "Link in bio to shop"}'
        )


@pytest.fixture
def sharp_image(tmp_path):
    img = (np.random.rand(1200, 1200, 3) * 255).astype("uint8")
    path = str(tmp_path / "sharp.jpg")
    cv2.imwrite(path, img)
    return path


@pytest.fixture
def blurry_image(tmp_path):
    img = np.full((1200, 1200, 3), 128, dtype="uint8")
    path = str(tmp_path / "blurry.jpg")
    cv2.imwrite(path, img)
    return path


@pytest.fixture
def config(tmp_path):
    return InstagramConfig(
        ig_feedback_store_path=str(tmp_path / "feedback.jsonl"),
        ig_post_threshold=0.5,
    )


def test_image_quality_analyzer_flags_blur(sharp_image, blurry_image, config):
    analyzer = ImageQualityAnalyzer(config)
    sharp_metrics = analyzer.analyze(sharp_image)
    blurry_metrics = analyzer.analyze(blurry_image)

    assert not sharp_metrics.is_blurry
    assert blurry_metrics.is_blurry
    assert sharp_metrics.quality_score > blurry_metrics.quality_score


def test_formatter_selects_layout(sharp_image, blurry_image, config, tmp_path):
    formatter = CreativeFormatter(config, output_dir=str(tmp_path / "processed"))

    single = formatter.format([sharp_image])
    assert single.layout_type == LayoutType.SINGLE_IMAGE
    assert single.brand_overlay_applied is False  # no branding configured

    carousel = formatter.format([sharp_image, blurry_image])
    assert carousel.layout_type == LayoutType.CAROUSEL
    assert len(carousel.media_paths) == 2


def test_feedback_store_category_stats(tmp_path):
    store = FeedbackStore(str(tmp_path / "fb.jsonl"))
    store.append(
        {
            "product_id": "p1",
            "category": "pottery",
            "engagement": {"likes": 10, "comments": 0, "shares": 0, "saves": 0, "reach": 100},
        }
    )
    stats = store.get_category_stats("pottery")
    assert stats["post_count"] == 1
    assert stats["avg_engagement_rate"] == pytest.approx(0.10)

    cold = store.get_category_stats("never_seen_category")
    assert cold["post_count"] == 0


def test_pipeline_holds_back_low_scoring_product(blurry_image, config):
    config.ig_post_threshold = 0.85
    pipeline = InstagramContentPipeline(config=config, llm_client=FakeLLM(uniqueness="2"))
    product = {
        "product_id": "p_low",
        "category": "pottery",
        "listing": {"description": "generic item"},
        "product_facts": {},
    }
    result = pipeline.process(product, image_paths=[blurry_image])
    assert result.status == PostStatus.HELD_BACK
    assert result.requeue_after is not None


def test_pipeline_full_flow_for_high_scoring_product(sharp_image, config):
    pipeline = InstagramContentPipeline(config=config, llm_client=FakeLLM(uniqueness="9"))
    product = {
        "product_id": "p_high",
        "category": "pottery",
        "listing": {"description": "A hand-thrown ceramic vase from Jaipur."},
        "product_facts": {"material": "clay", "origin": "Jaipur"},
    }
    result = pipeline.process(product, image_paths=[sharp_image])
    assert result.status == PostStatus.PENDING
    assert result.caption is not None
    assert result.layout is not None
    assert result.safety_result.safe is True
    assert result.scheduled_publish_time is not None


def test_pipeline_fails_safety_when_caption_incoherent(sharp_image, config):
    pipeline = InstagramContentPipeline(config=config, llm_client=FakeLLM(coherent="NO"))
    product = {
        "product_id": "p_mismatch",
        "category": "pottery",
        "listing": {"description": "A vase."},
        "product_facts": {},
    }
    result = pipeline.process(product, image_paths=[sharp_image])
    assert result.status == PostStatus.FAILED
    assert "safety" in result.error.lower()
