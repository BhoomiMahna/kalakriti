"""Top-level orchestrator for the Instagram content pipeline."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from .caption_generator import InstagramCaptionGenerator
from .config import InstagramConfig
from .feedback import FeedbackLoop
from .feedback_store import FeedbackStore
from .formatter import CreativeFormatter
from .instagram_schema import EngagementMetrics, PostStatus, ScheduledPost
from .llm_client import GeminiLLMClient, LLMClient
from .publisher import InstagramPublisher
from .safety import ContentSafetyChecker
from .scheduler import AutoScheduler
from .scorer import PostWorthinessScorer

logger = logging.getLogger(__name__)

# The Graph API requires publicly reachable image URLs -- it can't accept
# local file paths or raw bytes. Provide an uploader that pushes a local
# file to your CDN/bucket and returns its public URL.
MediaUploader = Callable[[str], str]


class InstagramContentPipeline:
    def __init__(
        self,
        config: Optional[InstagramConfig] = None,
        llm_client: Optional[LLMClient] = None,
        media_uploader: Optional[MediaUploader] = None,
    ):
        self.config = config or InstagramConfig()
        self.llm_client = llm_client or GeminiLLMClient(
            api_key=self.config.gemini_api_key,
            model=self.config.gemini_model,
        )
        self.media_uploader = media_uploader

        self.feedback_store = FeedbackStore(self.config.ig_feedback_store_path)
        self.scorer = PostWorthinessScorer(self.config, self.llm_client, self.feedback_store)
        self.safety_checker = ContentSafetyChecker(self.config, self.llm_client)
        self.caption_generator = InstagramCaptionGenerator(self.llm_client)
        self.formatter = CreativeFormatter(self.config)
        self.scheduler = AutoScheduler(self.config, self.feedback_store)
        self.publisher = InstagramPublisher(self.config)
        self.feedback_loop = FeedbackLoop(self.config, self.feedback_store, self.publisher)

    def process(
        self,
        product_output: dict,
        image_paths: list[str],
        has_video: bool = False,
        publish_immediately: bool = False,
    ) -> ScheduledPost:
        """
        Full flow:
          1. Score post-worthiness
          2. If below threshold -> return held_back status
          3. Run content safety checks
          4. Generate Instagram caption
          5. Format creative
          6. Calculate optimal publish time
          7. (Optionally) publish via Graph API
          8. Return ScheduledPost with status

        `product_output` is expected to have at least:
          {
            "product_id": str,
            "category": str,
            "listing": {"description": str, ...},
            "product_facts": {...},
          }
        Adjust the field lookups below once you wire in your real
        ArtisanProductPipeline output shape.

        `publish_immediately`: if False (default), the post is scored,
        checked, formatted and scheduled but NOT sent to the Graph API --
        useful for dry runs / review before you've configured credentials
        or a media uploader. Set True once ready to go live.
        """
        product_id = product_output["product_id"]
        category = product_output.get("category", "uncategorized")
        listing = product_output.get("listing", {})
        description = listing.get("description", "")
        product_facts = product_output.get("product_facts", {})

        worthiness = self.scorer.score(
            product_id=product_id,
            description=description,
            product_facts=product_facts,
            category=category,
            image_paths=image_paths,
        )
        logger.info("Product %s scored %.3f", product_id, worthiness.composite_score)

        scheduled = self.scheduler.gate(worthiness)
        if scheduled.status == PostStatus.HELD_BACK:
            return scheduled

        caption = self.caption_generator.generate(product_facts, listing)
        scheduled.caption = caption

        safety_result = self.safety_checker.check(image_paths, caption, product_facts)
        scheduled.safety_result = safety_result
        if not safety_result.safe:
            scheduled.status = PostStatus.FAILED
            scheduled.error = f"Failed safety checks: {'; '.join(safety_result.flags)}"
            logger.warning("Product %s failed safety checks: %s", product_id, safety_result.flags)
            return scheduled

        layout = self.formatter.format(image_paths, has_video=has_video)
        scheduled.layout = layout

        if not publish_immediately:
            scheduled.status = PostStatus.PENDING
            return scheduled

        return self._publish(scheduled, category=category)

    def _publish(self, scheduled: ScheduledPost, category: str = "uncategorized") -> ScheduledPost:
        if not self.media_uploader:
            scheduled.status = PostStatus.FAILED
            scheduled.error = (
                "No media_uploader configured -- the Graph API requires public "
                "image URLs. Pass media_uploader=<fn: local_path -> public_url> "
                "to InstagramContentPipeline()."
            )
            return scheduled

        try:
            image_urls = [self.media_uploader(p) for p in scheduled.layout.media_paths]
            post_id = self.publisher.publish(scheduled.layout, scheduled.caption, image_urls)
            scheduled.instagram_post_id = post_id
            scheduled.status = PostStatus.PUBLISHED
            scheduled.scheduled_publish_time = scheduled.scheduled_publish_time or datetime.utcnow()

            self.feedback_store.append(
                {
                    "product_id": scheduled.product_id,
                    "category": category,
                    "instagram_post_id": post_id,
                    "worthiness_score": scheduled.worthiness_score.composite_score,
                    "published_at": scheduled.scheduled_publish_time.isoformat(),
                    "engagement": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            scheduled.status = PostStatus.FAILED
            scheduled.error = str(exc)
            logger.exception("Failed to publish product %s", scheduled.product_id)

        return scheduled

    def collect_feedback(self, post_id: str) -> EngagementMetrics:
        """Poll engagement data for a published post."""
        return self.feedback_loop.collect(post_id)

    def recalibrate(self) -> dict:
        """Run the feedback loop's recalibration and return its recommendation."""
        return self.feedback_loop.recalibrate()
