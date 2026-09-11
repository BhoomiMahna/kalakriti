"""
InstagramService — the platform's bridge to the standalone Instagram pipeline.

Runs the package's scoring → safety → caption → creative → schedule flow on a
canonical product, then records the outcome as an InstagramPost. In DEMO mode
it simulates publishing (no Graph API, clearly labelled); in REAL mode it
publishes through the package's Graph API path using injected credentials + a
media uploader. Real credentials always win; missing creds fall back to demo.
"""
from __future__ import annotations

import logging
import random
import sys
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.config import settings
from models import InstagramPost, InstagramPostStatus, Product

from .config import build_instagram_config, has_real_credentials
from .llm import build_llm
from .mapper import resolve_image_paths, to_product_output
from .media import make_media_uploader

logger = logging.getLogger(__name__)

# Make the standalone `artisans_ai` package importable at module load.
if settings.repo_root not in sys.path:
    sys.path.insert(0, settings.repo_root)

_pipeline = None
_pipeline_llm_mode = None


def _get_pipeline():
    """Lazily build (and cache) the package pipeline."""
    global _pipeline, _pipeline_llm_mode
    if _pipeline is not None:
        return _pipeline
    if settings.repo_root not in sys.path:
        sys.path.insert(0, settings.repo_root)
    from artisans_ai.instagram import InstagramContentPipeline  # type: ignore

    llm = build_llm()
    _pipeline_llm_mode = type(llm).__name__
    _pipeline = InstagramContentPipeline(
        config=build_instagram_config(),
        llm_client=llm,
        media_uploader=make_media_uploader(),
    )
    logger.info("Instagram pipeline ready (llm=%s)", _pipeline_llm_mode)
    return _pipeline


def is_demo() -> bool:
    return settings.instagram_demo_mode or not has_real_credentials()


def evaluate_and_post(db: Session, product: Product) -> InstagramPost:
    """Score → safety → caption → creative → (demo/real) publish; persist result."""
    from artisans_ai.instagram.instagram_schema import PostStatus  # type: ignore

    post = InstagramPost(product_id=product.id, demo=is_demo(),
                         status=InstagramPostStatus.EVALUATING)
    db.add(post)
    db.commit()

    image_paths = resolve_image_paths(product)
    if not image_paths:
        post.status = InstagramPostStatus.FAILED
        post.error = "No local product images available for Instagram."
        db.commit()
        return post

    pipeline = _get_pipeline()
    product_output = to_product_output(product)
    demo = is_demo()

    try:
        result = pipeline.process(
            product_output,
            image_paths=image_paths,
            publish_immediately=(not demo),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Instagram pipeline crashed for %s", product.id)
        post.status = InstagramPostStatus.FAILED
        post.error = f"Pipeline error: {exc}"
        db.commit()
        return post

    # Common fields captured whenever available.
    if result.worthiness_score:
        post.score = result.worthiness_score.composite_score
        post.score_breakdown = {
            "image": result.worthiness_score.image_score,
            "story": result.worthiness_score.story_score,
            "category": result.worthiness_score.category_score,
            "notes": result.worthiness_score.notes,
        }
    if result.caption:
        post.caption_text = result.caption.caption_text
        post.hashtags = result.caption.hashtags
        post.call_to_action = result.caption.call_to_action
    if result.safety_result:
        post.safety_safe = result.safety_result.safe
        post.safety_flags = result.safety_result.flags
    if result.layout:
        post.layout_type = result.layout.layout_type.value
    post.scheduled_time = result.scheduled_publish_time

    if result.status == PostStatus.HELD_BACK:
        post.status = InstagramPostStatus.HELD_BACK
        post.error = "Below post-worthiness threshold — held for re-scoring."
    elif result.status == PostStatus.FAILED and result.safety_result and not result.safety_result.safe:
        post.status = InstagramPostStatus.UNSAFE
        post.error = result.error
    elif result.status == PostStatus.FAILED:
        post.status = InstagramPostStatus.FAILED
        post.error = result.error
    elif result.status == PostStatus.PUBLISHED:
        post.status = InstagramPostStatus.PUBLISHED
        post.instagram_post_id = result.instagram_post_id
        post.permalink = f"https://www.instagram.com/p/{result.instagram_post_id}/"
        post.image_urls = _public_urls(result)
    else:
        # PENDING — safe & formatted. Demo mode simulates the publish.
        if demo:
            _demo_publish(pipeline, post, result, product_output["category"])
        else:
            post.status = InstagramPostStatus.SCHEDULED
            post.image_urls = _public_urls(result)

    db.commit()
    return post


def _public_urls(result) -> list[str]:
    up = make_media_uploader()
    try:
        return [up(p) for p in (result.layout.media_paths if result.layout else [])]
    except Exception:  # noqa: BLE001
        return []


def _demo_publish(pipeline, post: InstagramPost, result, category: str) -> None:
    """Simulate a publish for the judge demo — clearly a demo, never claimed real."""
    ext = f"DEMO-IG-{post.product_id[:10].upper()}"
    post.image_urls = _public_urls(result)
    post.instagram_post_id = ext
    post.permalink = f"/demo/instagram/post/{ext}"
    post.status = InstagramPostStatus.DEMO_PUBLISHED
    # Record in the package feedback store so the 3-hour gap + category stats
    # + hourly-engagement logic all work across demo posts too.
    published_at = result.scheduled_publish_time or datetime.utcnow()
    try:
        pipeline.feedback_store.append({
            "product_id": post.product_id,
            "category": category,
            "instagram_post_id": ext,
            "worthiness_score": post.score,
            "published_at": published_at.isoformat(),
            "engagement": None,
        })
    except Exception:  # noqa: BLE001
        logger.exception("Failed to append demo feedback record")


def simulate_engagement(db: Session, post: InstagramPost) -> InstagramPost:
    """Fabricate plausible engagement for a demo post and store it (feedback loop)."""
    reach = random.randint(300, 1500)
    likes = int(reach * random.uniform(0.05, 0.14))
    comments = int(likes * random.uniform(0.03, 0.12))
    saves = int(likes * random.uniform(0.05, 0.2))
    shares = int(likes * random.uniform(0.02, 0.1))
    engagement = {"likes": likes, "comments": comments, "shares": shares,
                  "saves": saves, "reach": reach, "impressions": int(reach * 1.4)}
    post.engagement = engagement
    db.commit()

    # Feed the package's feedback store so recalibration/category-stats improve.
    try:
        pipeline = _get_pipeline()
        pipeline.feedback_store.append({
            "product_id": post.product_id,
            "category": (post.product.category if post.product else "Handicraft"),
            "instagram_post_id": post.instagram_post_id,
            "worthiness_score": post.score,
            "published_at": (post.scheduled_time or datetime.utcnow()).isoformat(),
            "engagement": engagement,
        })
    except Exception:  # noqa: BLE001
        logger.exception("Failed to record simulated engagement")
    return post


def collect_feedback(db: Session, post: InstagramPost) -> InstagramPost:
    """Real mode: pull Graph insights. Demo mode: simulate."""
    if post.demo or not post.instagram_post_id or not has_real_credentials():
        return simulate_engagement(db, post)
    try:
        metrics = _get_pipeline().collect_feedback(post.instagram_post_id)
        post.engagement = metrics.model_dump(mode="json")
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to collect Instagram feedback")
        post.error = f"Feedback error: {exc}"
        db.commit()
    return post


def recalibrate() -> dict:
    """Run the package feedback loop's threshold recalibration recommendation."""
    return _get_pipeline().recalibrate()


def mode_info() -> dict:
    return {
        "enabled": settings.instagram_enabled,
        "demo_mode": is_demo(),
        "account_handle": settings.instagram_account_handle,
        "llm": _pipeline_llm_mode or ("Gemini" if (settings.gemini_api_key or settings.google_api_key) else "Fallback"),
        "post_threshold": settings.instagram_post_threshold,
        "min_post_gap_hours": 3,
    }
