# artisan_ai.instagram

Autonomous Instagram content pipeline: scores products for post-worthiness,
runs safety checks, generates captions, formats creative, schedules/publishes,
and collects engagement feedback to recalibrate itself over time.

This was built **standalone** (no access to your actual `artisan_ai` codebase),
so a few integration points are stubbed with clear seams. Read this file
before wiring it in.

## What you confirmed vs. what's still assumed

Confirmed by you:
- **No branding yet.** `ig_apply_brand_overlay=False` and `ig_brand_logo_path=""`
  by default — images are still resized/cropped to Instagram's 1080×1080 spec,
  just without a watermark or border. Flip `ig_apply_brand_overlay=True` and
  set `ig_brand_logo_path` once you have a logo; the overlay code already works
  (tested with a synthetic image).
- **Single brand account**, not per-artisan. `InstagramConfig.ig_account_handle`
  is a single value; there's no per-artisan account routing anywhere in the
  package.
- **3-hour minimum gap** between auto-posts (`ig_min_post_gap_hours=3`).

Still using reasonable defaults you haven't confirmed — change freely in `config.py`:
- **Carousel support**: built to handle 1 image (single post) through 10
  images (carousel cap), so it works whether your pipeline sends one image or
  several per product. No behavior change needed either way.
- **Engagement polling frequency**: defaulted to every 6 hours
  (`ig_engagement_poll_hours`). This value isn't self-enforced by the
  pipeline — you call `pipeline.collect_feedback(post_id)` on whatever cron
  schedule you set up; the config field is just there for your scheduler to
  read.
- **Storage backend**: JSONL file (`FeedbackStore`), per the MVP suggestion in
  the spec. Query methods (`get_category_stats`, `get_hourly_engagement`,
  `get_recent_posts`) are written so swapping in SQLite later doesn't change
  any caller code.

## Integration seams you need to fill in

1. **LLM client** (`llm_client.py`): the pipeline uses `GeminiLLMClient` by
  default. Set `GEMINI_API_KEY` in the environment, or pass
  `gemini_api_key` and optionally `gemini_model` in `InstagramConfig`. You can
  still inject any object implementing `LLMClient` for tests or another provider.

2. **Media uploader** (`pipeline.py`): the Instagram Graph API requires
   *publicly reachable URLs* for images, not local paths. Pass a
   `media_uploader: Callable[[str], str]` (local path → public URL, e.g. an
   S3/GCS upload) into `InstagramContentPipeline(media_uploader=...)`. Without
   one, `process(..., publish_immediately=True)` will fail cleanly with a
   descriptive error rather than silently doing nothing.

3. **Config**: `config.py` currently defines a standalone `InstagramConfig`
   dataclass. Every module reads config by attribute name only, so you can
   either keep using this class as-is, or copy its fields directly into your
   existing `Config` class — no code changes needed either way.

4. **Credentials**: you still need a Meta Business Account, an Instagram
   Professional Account linked to it, and a registered Facebook App with
   `instagram_content_publish` and `instagram_manage_insights` permissions,
   with the resulting `ig_access_token` / `ig_business_account_id` set on
   `InstagramConfig`. Until then, run with `publish_immediately=False`
   (the default) — the pipeline scores, safety-checks, and formats posts
   without touching the Graph API, so you can review output before going live.

5. **Product output shape**: `pipeline.process()` expects:
   ```python
   {
     "product_id": str,
     "category": str,
     "listing": {"description": str, ...},
     "product_facts": {...},
   }
   ```
   Adjust the field lookups at the top of `InstagramContentPipeline.process()`
   once you confirm your real `ArtisanProductPipeline` output shape.

## What's been tested (offline, no network)

Since this sandbox has no network access, `pydantic`/`pytest` couldn't be
pip-installed here. I validated the actual logic two ways:
- Every file passes `python -m py_compile` (no syntax errors).
- I ran the real numeric/image logic (blur detection, resolution checks,
  layout selection, carousel truncation, feedback-store aggregation, the
  full `pipeline.process()` flow for both a high-scoring and a held-back
  product, and a safety-check failure path) against synthetic images and a
  fake LLM client, using a minimal pydantic-compatible shim standing in for
  the real library. All of it behaved as expected (see conversation for the
  actual runs).

`tests/test_instagram/test_pipeline.py` covers the same scenarios properly
with real `pytest` + `pydantic` — run it in your actual environment with:
```
pip install -r requirements_additions.txt
pytest tests/test_instagram/
```

## Known nits (not bugs, just worth knowing)

- `datetime.utcnow()` is used throughout (per Python's deprecation warning in
  3.12+, not a functional issue). Fine to leave; migrate to
  `datetime.now(timezone.utc)` opportunistically if you want to silence the
  warning.
- `FORBIDDEN_TERMS` / `MISLEADING_PATTERNS` in `safety.py` are placeholder
  examples — swap in your real moderation term list.
- `ImageQualityAnalyzer._composition_score()` is a cheap edge/exposure
  heuristic, not a real composition model — good enough to separate
  obviously bad shots from normal ones, not a substitute for anything more
  sophisticated if you need that later.
