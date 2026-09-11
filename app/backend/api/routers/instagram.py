"""Instagram automation endpoints — artisan-facing status, admin view, demo post."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.deps import get_current_artisan
from db.session import get_db
from integrations.instagram import service as ig
from models import Artisan, InstagramPost, InstagramPostStatus, Product

router = APIRouter(tags=["instagram"])

# Statuses that count as "in the content queue / posted" for the artisan view.
_QUEUED = {InstagramPostStatus.SCHEDULED, InstagramPostStatus.DEMO_PUBLISHED,
           InstagramPostStatus.PUBLISHED, InstagramPostStatus.EVALUATING}


def _post_dict(p: InstagramPost) -> dict:
    return {
        "id": p.id,
        "product_id": p.product_id,
        "product_title": p.product.title if p.product else None,
        "status": p.status.value,
        "demo": p.demo,
        "score": p.score,
        "score_breakdown": p.score_breakdown,
        "safety_safe": p.safety_safe,
        "safety_flags": p.safety_flags,
        "caption_text": p.caption_text,
        "hashtags": p.hashtags,
        "call_to_action": p.call_to_action,
        "layout_type": p.layout_type,
        "image_urls": p.image_urls,
        "scheduled_time": p.scheduled_time.isoformat() if p.scheduled_time else None,
        "instagram_post_id": p.instagram_post_id,
        "permalink": p.permalink,
        "engagement": p.engagement,
        "error": p.error,
    }


# ── Artisan-facing (simple, no internals) ────────────────────────────────────

@router.get("/products/{product_id}/instagram")
def product_instagram_status(
    product_id: str,
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> dict:
    product = db.get(Product, product_id)
    if not product or product.artisan_id != artisan.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    post = (
        db.query(InstagramPost)
        .filter(InstagramPost.product_id == product_id)
        .order_by(InstagramPost.created_at.desc())
        .first()
    )
    if not post:
        return {"state": "none"}
    # Map internal status to a simple artisan-facing state (frontend localizes).
    state = {
        InstagramPostStatus.EVALUATING: "queued",
        InstagramPostStatus.SCHEDULED: "scheduled",
        InstagramPostStatus.DEMO_PUBLISHED: "posted",
        InstagramPostStatus.PUBLISHED: "posted",
        InstagramPostStatus.HELD_BACK: "held",
        InstagramPostStatus.UNSAFE: "held",
        InstagramPostStatus.FAILED: "held",
    }[post.status]
    return {
        "state": state,
        "demo": post.demo,
        "scheduled_time": post.scheduled_time.isoformat() if post.scheduled_time else None,
        "permalink": post.permalink,
    }


# ── Admin / platform view ────────────────────────────────────────────────────

@router.get("/admin/instagram/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    counts = dict(
        db.query(InstagramPost.status, func.count(InstagramPost.id))
        .group_by(InstagramPost.status)
        .all()
    )

    def c(s: InstagramPostStatus) -> int:
        return int(counts.get(s, 0))

    scheduled_or_posted = (
        db.query(InstagramPost)
        .filter(InstagramPost.status.in_([InstagramPostStatus.SCHEDULED,
                                          InstagramPostStatus.DEMO_PUBLISHED]))
        .filter(InstagramPost.scheduled_time.isnot(None))
    )
    now = datetime.utcnow()
    next_post = (
        scheduled_or_posted.filter(InstagramPost.scheduled_time >= now)
        .order_by(InstagramPost.scheduled_time.asc())
        .first()
    )
    return {
        **ig.mode_info(),
        "evaluated": db.query(InstagramPost).count(),
        "selected": c(InstagramPostStatus.SCHEDULED) + c(InstagramPostStatus.DEMO_PUBLISHED) + c(InstagramPostStatus.PUBLISHED),
        "scheduled": c(InstagramPostStatus.SCHEDULED) + c(InstagramPostStatus.DEMO_PUBLISHED),
        "published": c(InstagramPostStatus.PUBLISHED) + c(InstagramPostStatus.DEMO_PUBLISHED),
        "held": c(InstagramPostStatus.HELD_BACK) + c(InstagramPostStatus.UNSAFE),
        "failed": c(InstagramPostStatus.FAILED),
        "next_post_time": next_post.scheduled_time.isoformat() if next_post else None,
    }


@router.get("/admin/instagram/posts")
def list_posts(db: Session = Depends(get_db), limit: int = 50) -> list[dict]:
    posts = (
        db.query(InstagramPost)
        .order_by(InstagramPost.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_post_dict(p) for p in posts]


@router.post("/admin/instagram/evaluate/{product_id}")
def evaluate(product_id: str, db: Session = Depends(get_db)) -> dict:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    post = ig.evaluate_and_post(db, product)
    return _post_dict(post)


@router.post("/admin/instagram/posts/{post_id}/simulate-engagement")
def simulate(post_id: str, db: Session = Depends(get_db)) -> dict:
    post = db.get(InstagramPost, post_id)
    if not post:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    ig.simulate_engagement(db, post)
    return _post_dict(post)


@router.post("/admin/instagram/recalibrate")
def recalibrate(db: Session = Depends(get_db)) -> dict:
    return ig.recalibrate()


# ── Public demo Instagram post page ──────────────────────────────────────────

@router.get("/public/instagram/post/{external_id}")
def demo_post(external_id: str, db: Session = Depends(get_db)) -> dict:
    post = (
        db.query(InstagramPost)
        .filter(InstagramPost.instagram_post_id == external_id)
        .first()
    )
    if not post:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Instagram post not found")
    product = post.product
    return {
        "external_id": external_id,
        "is_demo": post.demo,
        "account_handle": ig.mode_info()["account_handle"],
        "caption_text": post.caption_text,
        "hashtags": post.hashtags or [],
        "call_to_action": post.call_to_action,
        "images": post.image_urls or [],
        "layout_type": post.layout_type,
        "product_title": product.title if product else None,
        "price": product.price if product else None,
        "currency": product.currency if product else "INR",
        "artisan_name": product.artisan.name if (product and product.artisan) else None,
        "engagement": post.engagement,
    }
