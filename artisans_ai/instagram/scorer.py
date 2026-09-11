"""Post-worthiness scoring: is this product worth posting to Instagram?"""

from __future__ import annotations

import logging
import re
from typing import Optional

import cv2
import numpy as np

from .config import InstagramConfig
from .feedback_store import FeedbackStore
from .instagram_schema import ImageQualityMetrics, PostWorthinessScore
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

VALID_ASPECT_RATIOS = {
    "1:1": 1.0,
    "4:5": 0.8,
    "1.91:1": 1.91,
}
ASPECT_RATIO_TOLERANCE = 0.05


class ImageQualityAnalyzer:
    """Rule-based image quality checks -- no ML model needed."""

    def __init__(self, config: InstagramConfig):
        self.config = config

    def analyze(self, image_path: str) -> ImageQualityMetrics:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image at {image_path}")

        height, width = img.shape[:2]
        aspect_ratio = round(width / height, 3)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_blurry = blur_score < self.config.ig_blur_threshold_scorer

        meets_min_resolution = min(width, height) >= self.config.ig_min_resolution_px

        aspect_ratio_valid = any(
            abs(aspect_ratio - target) <= ASPECT_RATIO_TOLERANCE
            for target in VALID_ASPECT_RATIOS.values()
        )

        composition_score = self._composition_score(gray)

        quality_score = self._composite_quality_score(
            blur_score=blur_score,
            meets_min_resolution=meets_min_resolution,
            aspect_ratio_valid=aspect_ratio_valid,
            composition_score=composition_score,
        )

        return ImageQualityMetrics(
            image_path=image_path,
            blur_score=blur_score,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            is_blurry=is_blurry,
            meets_min_resolution=meets_min_resolution,
            aspect_ratio_valid=aspect_ratio_valid,
            composition_score=composition_score,
            quality_score=quality_score,
        )

    @staticmethod
    def _composition_score(gray_img: np.ndarray) -> float:
        """
        Cheap proxy for 'is the subject reasonably centered / well-exposed':
        combines exposure balance with a rule-of-thirds edge-energy check.
        Not a substitute for a real composition model -- good enough to
        separate obviously bad shots (blown-out, subject in a corner) from
        normal ones.
        """
        mean_brightness = float(gray_img.mean())
        exposure_score = 1.0 - min(abs(mean_brightness - 127.5) / 127.5, 1.0)

        h, w = gray_img.shape
        edges = cv2.Canny(gray_img, 50, 150)
        third_h, third_w = h // 3, w // 3
        center_region = edges[third_h : 2 * third_h, third_w : 2 * third_w]
        center_energy = float(center_region.mean()) if center_region.size else 0.0
        total_energy = float(edges.mean()) if edges.size else 1.0
        center_ratio = min(center_energy / total_energy, 2.0) / 2.0 if total_energy > 0 else 0.5

        return round(0.5 * exposure_score + 0.5 * center_ratio, 3)

    def _composite_quality_score(
        self,
        blur_score: float,
        meets_min_resolution: bool,
        aspect_ratio_valid: bool,
        composition_score: float,
    ) -> float:
        blur_component = min(blur_score / (self.config.ig_blur_threshold_scorer * 3), 1.0)
        resolution_component = 1.0 if meets_min_resolution else 0.0
        aspect_component = 1.0 if aspect_ratio_valid else 0.3  # not disqualifying, just penalized

        score = (
            0.4 * blur_component
            + 0.3 * resolution_component
            + 0.15 * aspect_component
            + 0.15 * composition_score
        )
        return round(max(0.0, min(1.0, score)), 3)


class StoryUniquenessScorer:
    """LLM-based rating of how interesting/unique a product's story is."""

    SYSTEM_PROMPT = (
        "You are a social media content strategist for a handmade artisan "
        "marketplace. Given a product's description and facts, rate how "
        "unique and story-worthy it is for an Instagram audience compared to "
        "a generic, mass-produced version of the same item. Consider "
        "craftsmanship details, cultural/personal narrative, materials, and "
        "anything that would make a scroller stop and read. "
        "Respond with ONLY a single integer from 1 to 10, nothing else."
    )

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def score(self, description: str, product_facts: dict) -> float:
        user_prompt = (
            f"Product description:\n{description}\n\n"
            f"Product facts:\n{product_facts}\n\n"
            "Uniqueness rating (1-10):"
        )
        try:
            raw = self.llm_client.complete(self.SYSTEM_PROMPT, user_prompt, temperature=0.2)
        except NotImplementedError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("StoryUniquenessScorer LLM call failed, defaulting to 0.5: %s", exc)
            return 0.5

        match = re.search(r"\d+", raw)
        if not match:
            logger.warning("Could not parse uniqueness rating from LLM output: %r", raw)
            return 0.5

        rating = max(1, min(10, int(match.group())))
        return round(rating / 10.0, 3)


class CategoryPerformanceTracker:
    """Looks up historical engagement performance for a product's category."""

    COLD_START_SCORE = 0.5

    def __init__(self, feedback_store: FeedbackStore):
        self.feedback_store = feedback_store

    def score(self, category: str) -> tuple[float, bool]:
        """Returns (score, is_cold_start)."""
        stats = self.feedback_store.get_category_stats(category)
        if not stats or stats.get("post_count", 0) == 0:
            return self.COLD_START_SCORE, True

        avg_engagement_rate = stats.get("avg_engagement_rate", 0.0)
        # Normalize: treat a 10% engagement rate as "excellent" (score 1.0).
        # Tune this ceiling once you have real distribution data.
        normalized = min(avg_engagement_rate / 0.10, 1.0)
        return round(normalized, 3), False


class PostWorthinessScorer:
    """Combines image quality + story uniqueness + category history into one score."""

    def __init__(
        self,
        config: InstagramConfig,
        llm_client: LLMClient,
        feedback_store: FeedbackStore,
    ):
        self.config = config
        self.image_analyzer = ImageQualityAnalyzer(config)
        self.story_scorer = StoryUniquenessScorer(llm_client)
        self.category_tracker = CategoryPerformanceTracker(feedback_store)

    def score(
        self,
        product_id: str,
        description: str,
        product_facts: dict,
        category: str,
        image_paths: list[str],
    ) -> PostWorthinessScore:
        if not image_paths:
            raise ValueError("At least one image is required to score a post.")

        image_metrics = [self.image_analyzer.analyze(p) for p in image_paths]
        image_score = round(sum(m.quality_score for m in image_metrics) / len(image_metrics), 3)

        story_score = self.story_scorer.score(description, product_facts)
        category_score, is_cold_start = self.category_tracker.score(category)

        weights = self.config.ig_scorer_weights
        composite = (
            weights.get("image", 0.30) * image_score
            + weights.get("story", 0.45) * story_score
            + weights.get("category", 0.25) * category_score
        )

        notes = []
        if any(m.is_blurry for m in image_metrics):
            notes.append("One or more images flagged as blurry.")
        if not all(m.meets_min_resolution for m in image_metrics):
            notes.append(f"One or more images below {self.config.ig_min_resolution_px}px minimum.")
        if is_cold_start:
            notes.append(f"Category '{category}' has no engagement history yet (cold start).")

        return PostWorthinessScore(
            product_id=product_id,
            image_score=image_score,
            story_score=story_score,
            category_score=category_score,
            composite_score=round(max(0.0, min(1.0, composite)), 3),
            weights_used=dict(weights),
            is_cold_start_category=is_cold_start,
            notes=notes,
        )
