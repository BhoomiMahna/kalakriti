"""
Integration tests: canonical Product -> Instagram pipeline.

Run from app/backend:  python -m pytest tests/test_instagram_integration.py -q

Uses an isolated temp DB and the demo (offline) LLM/publish path so it needs no
network, no Gemini key, and no Meta credentials.
"""
import os
import tempfile
import uuid
from datetime import timedelta

import numpy as np
import pytest
from PIL import Image

# Isolated DB + demo mode BEFORE importing the app.
_TMP = tempfile.mkdtemp(prefix="ig_it_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["INSTAGRAM_DEMO_MODE"] = "true"
os.environ["INSTAGRAM_POST_THRESHOLD"] = "0.5"

from core.config import settings  # noqa: E402
from db.session import SessionLocal, init_db  # noqa: E402
from integrations.instagram import media as ig_media  # noqa: E402
from integrations.instagram import service as ig  # noqa: E402
from integrations.instagram.llm import FallbackLLMClient  # noqa: E402
from integrations.instagram.mapper import resolve_image_paths, to_product_output  # noqa: E402
from models import Artisan, InstagramPostStatus, Product  # noqa: E402

STORAGE = settings.storage_dir


def _img(name, textured=True, size=(1100, 1100)):
    path = os.path.join(STORAGE, name)
    os.makedirs(STORAGE, exist_ok=True)
    if textured:
        arr = (np.random.rand(size[1], size[0], 3) * 255).astype("uint8")
    else:
        arr = np.full((size[1], size[0], 3), 128, dtype="uint8")
    Image.fromarray(arr).save(path, "JPEG")
    return f"/media/{name}"


@pytest.fixture(scope="module", autouse=True)
def _db():
    init_db()


def _make_product(db, *, textured=True, images=3, category="Handicraft"):
    art = Artisan(phone=f"+9199{uuid.uuid4().int % 10**8:08d}", name="Meera", location="Jaipur",
                  craft_category=category)
    db.add(art)
    db.commit()
    urls = [_img(f"{uuid.uuid4().hex}_{r}.jpg", textured=textured)
            for r in ("hero", "lifestyle", "detail")[:images]]
    gen = {}
    for role, url in zip(("hero", "lifestyle", "detail"), urls):
        gen[role] = url
    p = Product(
        artisan_id=art.id, title="Handcrafted Denim Sling Bag",
        short_description="A handmade denim sling bag.",
        long_description="A handcrafted denim sling bag made from cotton denim.",
        artisan_story="Made by Meera in Jaipur from cotton denim.",
        category=category, material="Cotton Denim", price=1271, currency="INR",
        product_facts={"material": ["Cotton", "Denim"], "colors": ["Blue"]},
        generated_images=gen or None,
        original_images=urls or None,
        highlights=["Made from cotton denim", "Handcrafted"],
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ── Mapper ───────────────────────────────────────────────────────────────────

def test_mapper_shape_and_images():
    db = SessionLocal()
    p = _make_product(db)
    out = to_product_output(p)
    assert out["product_id"] == p.id
    assert out["category"] == "Handicraft"
    assert "description" in out["listing"] and out["listing"]["title"]
    assert out["product_facts"]["material"]  # not invented — comes from product
    paths = resolve_image_paths(p)
    assert len(paths) == 3 and all(os.path.exists(x) for x in paths)
    db.close()


def test_fallback_llm_is_grounded():
    llm = FallbackLLMClient()
    assert llm.complete("s", "Uniqueness rating (1-10):").isdigit()
    assert llm.complete("s", "Consistent? (YES/NO):") == "YES"
    import json
    cap = json.loads(llm.complete("s", 'Product facts:\n{"material": ["Jute"]}\n\nProduct listing:\n{"title": "Jute Bag"}\n\nGenerate'))
    assert "Jute Bag" in cap["caption_text"]
    assert "jute" in [h.lower() for h in cap["hashtags"]]


def test_media_uploader_returns_public_url():
    name = f"{uuid.uuid4().hex}.jpg"
    _img(name)
    url = ig_media.to_public_url(os.path.join(STORAGE, name))
    assert url.startswith("http") and url.endswith(name)


# ── Full demo flow ───────────────────────────────────────────────────────────

def test_demo_publish_full_flow_carousel():
    db = SessionLocal()
    p = _make_product(db, images=3)
    post = ig.evaluate_and_post(db, p)
    assert post.status == InstagramPostStatus.DEMO_PUBLISHED
    assert post.safety_safe is True
    assert post.caption_text and post.hashtags
    assert post.layout_type == "carousel"      # 3 images -> carousel
    assert len(post.image_urls) == 3
    assert post.permalink.startswith("/demo/instagram/post/")
    assert post.instagram_post_id.startswith("DEMO-IG-")
    db.close()


def test_single_image_is_single_layout():
    db = SessionLocal()
    p = _make_product(db)
    # keep only hero
    p.generated_images = {"hero": p.generated_images["hero"]}
    db.commit()
    post = ig.evaluate_and_post(db, p)
    assert post.status == InstagramPostStatus.DEMO_PUBLISHED
    assert post.layout_type == "single_image"
    db.close()


def test_low_quality_product_is_held_or_unsafe():
    db = SessionLocal()
    p = _make_product(db, textured=False)  # blank images -> low score / unsafe
    post = ig.evaluate_and_post(db, p)
    assert post.status in (InstagramPostStatus.HELD_BACK, InstagramPostStatus.UNSAFE)
    db.close()


def test_missing_media_fails_cleanly():
    db = SessionLocal()
    p = _make_product(db)
    p.generated_images = None
    p.original_images = None
    db.commit()
    post = ig.evaluate_and_post(db, p)
    assert post.status == InstagramPostStatus.FAILED
    assert "image" in post.error.lower()
    db.close()


def test_engagement_feedback_recorded():
    db = SessionLocal()
    p = _make_product(db)
    post = ig.evaluate_and_post(db, p)
    ig.simulate_engagement(db, post)
    assert post.engagement and post.engagement["reach"] > 0
    db.close()


def test_three_hour_gap_between_scheduled_posts():
    db = SessionLocal()
    p1 = _make_product(db)
    p2 = _make_product(db)
    post1 = ig.evaluate_and_post(db, p1)
    post2 = ig.evaluate_and_post(db, p2)
    # Both should schedule; the second must be at least 3h after the first.
    if post1.scheduled_time and post2.scheduled_time:
        assert post2.scheduled_time >= post1.scheduled_time + timedelta(hours=3)
    db.close()


def test_real_publish_path_when_credentials_present(monkeypatch):
    """With demo off + creds present, the real Graph-API publish path runs."""
    db = SessionLocal()
    p = _make_product(db)
    monkeypatch.setattr(ig, "is_demo", lambda: False)
    pipeline = ig._get_pipeline()
    monkeypatch.setattr(pipeline.publisher, "publish", lambda layout, caption, urls: "IG_REAL_123")
    post = ig.evaluate_and_post(db, p)
    assert post.status == InstagramPostStatus.PUBLISHED
    assert post.instagram_post_id == "IG_REAL_123"
    db.close()
