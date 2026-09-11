"""Engagement feedback loop: collect insights, recalibrate scoring, tune threshold."""

from __future__ import annotations

import logging
from datetime import datetime

from .config import InstagramConfig
from .feedback_store import FeedbackStore
from .instagram_schema import EngagementMetrics
from .publisher import InstagramPublisher

logger = logging.getLogger(__name__)

# A "high-performing" post: composite score in top half of the 0-1 range,
# with an engagement rate above this floor.
HIGH_SCORE_THRESHOLD = 0.7
GOOD_ENGAGEMENT_RATE = 0.03  # 3% -- tune once you have real data
MIN_POSTS_FOR_RECALIBRATION = 50
ACCURACY_TARGET = 0.80
THRESHOLD_STEP = 0.02


class FeedbackLoop:
    def __init__(
        self,
        config: InstagramConfig,
        feedback_store: FeedbackStore,
        publisher: InstagramPublisher,
    ):
        self.config = config
        self.feedback_store = feedback_store
        self.publisher = publisher

    def collect(self, instagram_post_id: str) -> EngagementMetrics:
        return self.publisher.get_post_insights(instagram_post_id)

    def record(
        self,
        product_id: str,
        category: str,
        instagram_post_id: str,
        worthiness_score: float,
        published_at: datetime,
        engagement: EngagementMetrics,
    ) -> None:
        self.feedback_store.append(
            {
                "product_id": product_id,
                "category": category,
                "instagram_post_id": instagram_post_id,
                "worthiness_score": worthiness_score,
                "published_at": published_at.isoformat(),
                "engagement": engagement.model_dump(mode="json"),
            }
        )

    def recalibrate(self) -> dict:
        """
        Checks recent posts: do high-score posts actually get high engagement?
        If accuracy exceeds ACCURACY_TARGET over enough posts, relax the
        threshold slightly (down to the configured floor).

        Returns a summary dict; does NOT mutate self.config in place since
        InstagramConfig is meant to be reloaded/persisted by the caller --
        apply `new_threshold` yourself if you accept the recommendation.
        """
        posts = self.feedback_store.get_recent_posts(days=90)
        scored_posts = [p for p in posts if p.get("worthiness_score") is not None and p.get("engagement")]

        if len(scored_posts) < MIN_POSTS_FOR_RECALIBRATION:
            return {
                "recalibrated": False,
                "reason": f"Only {len(scored_posts)} posts with data, need {MIN_POSTS_FOR_RECALIBRATION}.",
                "current_threshold": self.config.ig_post_threshold,
            }

        correct = 0
        for p in scored_posts:
            score = p["worthiness_score"]
            eng = p["engagement"]
            reach = eng.get("reach", 0)
            if reach <= 0:
                continue
            rate = (
                eng.get("likes", 0) + eng.get("comments", 0) + eng.get("shares", 0) + eng.get("saves", 0)
            ) / reach
            predicted_high = score >= HIGH_SCORE_THRESHOLD
            actual_high = rate >= GOOD_ENGAGEMENT_RATE
            if predicted_high == actual_high:
                correct += 1

        accuracy = correct / len(scored_posts)
        new_threshold = self.config.ig_post_threshold

        if accuracy >= ACCURACY_TARGET:
            new_threshold = round(
                max(self.config.ig_threshold_floor, self.config.ig_post_threshold - THRESHOLD_STEP), 3
            )
            logger.info(
                "Model accuracy %.1f%% over %d posts exceeds target -- recommending threshold %.2f -> %.2f",
                accuracy * 100,
                len(scored_posts),
                self.config.ig_post_threshold,
                new_threshold,
            )

        return {
            "recalibrated": new_threshold != self.config.ig_post_threshold,
            "accuracy": round(accuracy, 3),
            "posts_evaluated": len(scored_posts),
            "current_threshold": self.config.ig_post_threshold,
            "recommended_threshold": new_threshold,
        }
