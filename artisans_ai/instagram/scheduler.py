"""Auto-scheduling: threshold gate + optimal publish time calculation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from .config import InstagramConfig
from .feedback_store import FeedbackStore
from .instagram_schema import PostStatus, PostWorthinessScore, ScheduledPost

logger = logging.getLogger(__name__)

# Cold-start defaults (IST), used until enough real engagement data exists.
DEFAULT_HIGH_ENGAGEMENT_HOURS = [9, 10, 19, 20]


class OptimalTimeCalculator:
    def __init__(self, config: InstagramConfig, feedback_store: FeedbackStore):
        self.config = config
        self.feedback_store = feedback_store

    def next_slot(self, after: datetime | None = None) -> datetime:
        """
        Picks the next publish time that:
          - respects the minimum gap since the last published post
          - lands in a historically high-engagement hour (or the cold-start
            defaults if there's not enough data yet)
        """
        now = after or datetime.utcnow()

        earliest_allowed = now
        last_published = self.feedback_store.last_published_at()
        if last_published:
            min_gap = timedelta(hours=self.config.ig_min_post_gap_hours)
            earliest_allowed = max(earliest_allowed, last_published + min_gap)

        good_hours = self._good_hours()

        candidate = earliest_allowed
        # Search forward hour-by-hour (capped at 7 days) for the next good slot.
        for _ in range(24 * 7):
            if candidate.hour in good_hours and candidate >= earliest_allowed:
                return candidate.replace(minute=0, second=0, microsecond=0)
            candidate += timedelta(hours=1)

        # Fallback -- shouldn't happen given good_hours is non-empty.
        return earliest_allowed

    def _good_hours(self) -> set[int]:
        hourly = self.feedback_store.get_hourly_engagement()
        if len(hourly) < 5:  # not enough data yet, use cold-start defaults
            return set(DEFAULT_HIGH_ENGAGEMENT_HOURS)

        # Top third of hours by average engagement rate.
        sorted_hours = sorted(hourly.items(), key=lambda kv: kv[1], reverse=True)
        top_n = max(1, len(sorted_hours) // 3)
        return {h for h, _ in sorted_hours[:top_n]}


class AutoScheduler:
    def __init__(self, config: InstagramConfig, feedback_store: FeedbackStore):
        self.config = config
        self.feedback_store = feedback_store
        self.time_calculator = OptimalTimeCalculator(config, feedback_store)

    def gate(self, worthiness: PostWorthinessScore) -> ScheduledPost:
        """
        Applies the threshold gate. Does NOT publish -- just decides whether
        this post proceeds to scheduling or gets held back.
        """
        if worthiness.composite_score >= self.config.ig_post_threshold:
            publish_time = self.time_calculator.next_slot()
            return ScheduledPost(
                product_id=worthiness.product_id,
                worthiness_score=worthiness,
                scheduled_publish_time=publish_time,
                status=PostStatus.PENDING,
            )

        requeue_after = datetime.utcnow() + timedelta(days=self.config.ig_requeue_days)
        logger.info(
            "Product %s scored %.3f, below threshold %.2f -- holding back, requeue after %s",
            worthiness.product_id,
            worthiness.composite_score,
            self.config.ig_post_threshold,
            requeue_after.isoformat(),
        )
        return ScheduledPost(
            product_id=worthiness.product_id,
            worthiness_score=worthiness,
            status=PostStatus.HELD_BACK,
            requeue_after=requeue_after,
        )
