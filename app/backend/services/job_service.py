"""
Async orchestration (spec §19, §22).

Long-running work (AI pipeline, marketplace publishing) runs in a background
thread with its OWN DB session, so the artisan's request returns immediately
and the frontend polls Job.steps for progress. Every step is persisted, so a
crash never loses product data and channels publish independently — one
marketplace failing does not stop another.

This uses a threadpool for simplicity (no Redis/Celery needed for the MVP);
the JobService interface is the seam where a real queue would drop in.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from db.session import SessionLocal
from models import (
    ChannelStatus,
    Job,
    JobStatus,
    Product,
    ProductChannel,
    ProductStatus,
)
from marketplace.registry import get_adapter
from services.ai_service import get_ai_service
from services.image_service import get_photoshoot_service
from services.inference import infer_pricing_inputs
from services.pricing_service import get_pricing_service

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job")
# Isolated pool for the (potentially slow) photoshoot so a bounded wait never
# starves the main job workers.
_photo_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="photo")
_lock = threading.Lock()


# ── Step helpers ─────────────────────────────────────────────────────────────

def _steps_template(kind: str) -> list[dict[str, Any]]:
    if kind == "ai_pipeline":
        labels = [
            ("understand", "Understanding your product"),
            ("photos", "Creating professional product photos"),
            ("transcribe", "Converting your voice to text"),
            ("describe", "Generating product description"),
            ("story", "Generating your artisan story"),
            ("price", "Calculating the recommended price"),
            ("assemble", "Preparing your marketplace listing"),
        ]
    else:  # publish
        labels = [("publish", "Publishing to marketplaces")]
    return [{"key": k, "label": l, "status": "pending"} for k, l in labels]


def _set_step(job: Job, key: str, status: str, detail: str = "") -> None:
    # Rebuild as fresh dicts and flag the JSON column dirty so SQLAlchemy
    # reliably persists the mutation.
    steps = [dict(s) for s in (job.steps or [])]
    for s in steps:
        if s["key"] == key:
            s["status"] = status
            if detail:
                s["detail"] = detail
    job.steps = steps
    job.updated_at = datetime.now(timezone.utc)
    flag_modified(job, "steps")


# ── Public API ───────────────────────────────────────────────────────────────

def start_ai_pipeline(product_id: str, inputs: dict[str, Any]) -> Job:
    """Create + enqueue the AI pipeline job. Returns the QUEUED job."""
    with SessionLocal() as db:
        job = Job(product_id=product_id, kind="ai_pipeline", status=JobStatus.QUEUED,
                  steps=_steps_template("ai_pipeline"))
        db.add(job)
        product = db.get(Product, product_id)
        if product:
            product.status = ProductStatus.AI_PROCESSING
        db.commit()
        job_id = job.id
    _executor.submit(_run_ai_pipeline, job_id, inputs)
    with SessionLocal() as db:
        return db.get(Job, job_id)


def start_instagram(product_id: str) -> None:
    """Enqueue the platform-level Instagram eligibility/content job (background)."""
    from core.config import settings as _s
    if not _s.instagram_enabled:
        return
    _executor.submit(_run_instagram, product_id)


def _run_instagram(product_id: str) -> None:
    db: Session = SessionLocal()
    try:
        product = db.get(Product, product_id)
        if not product:
            return
        from integrations.instagram import service as ig
        ig.evaluate_and_post(db, product)
    except Exception:  # noqa: BLE001
        logger.exception("Instagram eligibility job failed for %s", product_id)
    finally:
        db.close()


def run_photoshoot(product: Product, description: str = "") -> None:
    """Run the AI photoshoot for a product and set generated_images.

    Failed shots stay None (the UI shows a retry) — the original photo is never
    relabelled as an AI-generated shot.
    """
    from pathlib import Path
    from core.config import settings
    photoshoot = get_photoshoot_service()
    originals = product.original_images or []
    if not originals:
        product.generated_images = {"mode": "failed", "statuses": {}, "original": None}
        product.enhanced_images = None
        return
    try:
        import uuid
        from concurrent.futures import TimeoutError as FuturesTimeout
        src_name = Path(originals[0]).name
        src_path = Path(settings.storage_dir) / src_name
        # Unique base per (re)generation so new outputs bust any browser cache.
        base = f"{src_name.rsplit('.', 1)[0]}_{uuid.uuid4().hex[:6]}"
        # Run under a hard deadline: a known demo image resolves in well under a
        # second, but an unknown image on a slow/low-memory host could otherwise
        # block the whole listing pipeline forever. On timeout we mark the shots
        # failed (the UI shows a retry) instead of hanging.
        future = _photo_executor.submit(
            photoshoot.generate,
            str(src_path), settings.storage_dir,
            base_name=base,
            category=product.category or "",
            material=product.material or "",
            description=description or (product.short_description or ""),
        )
        try:
            shots = future.result(timeout=settings.photoshoot_timeout_seconds)
        except FuturesTimeout:
            logger.warning("[IMAGE] Photoshoot exceeded %ss deadline — marking failed "
                           "so the listing can complete (product %s)",
                           settings.photoshoot_timeout_seconds, product.id)
            product.generated_images = {
                "mode": "failed", "statuses": {}, "original": originals[0],
                "error": "timeout",
            }
            product.enhanced_images = None
            return
        gen = {"mode": shots.get("mode"), "statuses": shots.get("statuses", {}),
               "original": originals[0]}
        for role in ("hero", "lifestyle", "detail"):
            gen[role] = f"/media/{shots[role]}" if shots.get(role) else None
        product.generated_images = gen
        ready = [gen[r] for r in ("hero", "lifestyle", "detail") if gen.get(r)]
        product.enhanced_images = ready or None
    except Exception:  # noqa: BLE001
        logger.exception("[IMAGE] Photoshoot pipeline crashed")
        product.generated_images = {"mode": "failed", "statuses": {}, "original": originals[0]}
        product.enhanced_images = None


def regenerate_photoshoot(product_id: str) -> None:
    """Re-run just the photoshoot step (manual retry) and persist."""
    db: Session = SessionLocal()
    try:
        product = db.get(Product, product_id)
        if product:
            run_photoshoot(product, description=product.short_description or "")
            db.commit()
    finally:
        db.close()


def start_publish(product_id: str, channels: list[str]) -> Job:
    with SessionLocal() as db:
        job = Job(product_id=product_id, kind="publish", status=JobStatus.QUEUED,
                  steps=_steps_template("publish"))
        db.add(job)
        product = db.get(Product, product_id)
        if product:
            product.status = ProductStatus.PUBLISHING
            # Ensure a channel row exists per requested channel.
            existing = {c.channel for c in product.channels}
            for ch in channels:
                if ch not in existing:
                    db.add(ProductChannel(product_id=product_id, channel=ch,
                                          status=ChannelStatus.PENDING))
        db.commit()
        job_id = job.id
    _executor.submit(_run_publish, job_id, channels)
    with SessionLocal() as db:
        return db.get(Job, job_id)


# ── Workers ──────────────────────────────────────────────────────────────────

def _run_ai_pipeline(job_id: str, inputs: dict[str, Any]) -> None:
    db: Session = SessionLocal()
    try:
        job = db.get(Job, job_id)
        product = db.get(Product, job.product_id)
        job.status = JobStatus.RUNNING
        _set_step(job, "understand", "running"); db.commit()

        from core.config import settings
        from pathlib import Path
        _set_step(job, "understand", "done"); db.commit()

        # 1. AI Product Photoshoot: 1 basic photo -> hero / lifestyle / detail --
        _set_step(job, "photos", "running"); db.commit()
        run_photoshoot(product, description=inputs.get("text_hint", ""))
        _set_step(job, "photos", "done"); db.commit()

        # 2 + 3. Transcript -> English (for marketplace copy) -----------------
        _set_step(job, "transcribe", "running"); db.commit()
        lang = inputs.get("language", "en")
        confirmed = (inputs.get("confirmed_transcript") or "").strip()
        english_text = inputs.get("text_hint", "")
        original_transcript = confirmed
        if confirmed and lang and lang != "en":
            # Marketplace content is English; translate the confirmed transcript.
            from services.sarvam_service import get_sarvam_service
            translated = get_sarvam_service().translate_text(confirmed, lang, "en")
            english_text = translated or confirmed

        ai = get_ai_service()
        result = ai.process(
            audio_path=inputs.get("audio_path"),
            text_hint=english_text,
            product_name=inputs.get("product_name", ""),
            category=inputs.get("category", ""),
            material=inputs.get("material", ""),
            dimensions=inputs.get("dimensions", ""),
            artisan_name=inputs.get("artisan_name", ""),
            region=inputs.get("region", ""),
            language=lang,
        )
        _set_step(job, "transcribe", "done", detail=ai.mode); db.commit()

        _set_step(job, "describe", "running"); db.commit()
        listing = result.get("listing", {})
        # Keep the artisan-facing transcript in the spoken language.
        product.transcription = original_transcript or result.get("transcription", {}).get("original")
        product.title = listing.get("title")
        product.short_description = listing.get("short_description")
        product.long_description = listing.get("description")
        product.highlights = listing.get("highlights")
        product.keywords = listing.get("keywords")
        product.product_facts = result.get("product_facts")
        product.validation = result.get("validation")
        product.follow_up_questions = result.get("follow_up_questions")
        product.ai_result = result
        facts = result.get("product_facts") or {}
        if facts.get("material") and not product.material:
            mat = facts["material"]
            product.material = ", ".join(mat) if isinstance(mat, list) else str(mat)
        if facts.get("dimensions") and not product.dimensions:
            product.dimensions = str(facts["dimensions"])
        _set_step(job, "describe", "done"); db.commit()

        # 3b. Artisan story ---------------------------------------------------
        _set_step(job, "story", "running"); db.commit()
        product.artisan_story = result.get("story") or _story_from(result)
        _set_step(job, "story", "done"); db.commit()

        # 4. Pricing ----------------------------------------------------------
        _set_step(job, "price", "running"); db.commit()
        pricing = get_pricing_service()
        meta = pricing.metadata()
        # Auto-detect pricing inputs from what the artisan said — no form.
        spoken = " ".join(filter(None, [
            product.transcription, inputs.get("text_hint"), product.title,
            product.short_description,
        ]))
        detected = infer_pricing_inputs(
            spoken, product.product_facts,
            meta.get("categories", []), meta.get("materials", []),
            category_hint=product.category or "",
            material_hint=product.material or "",
        )
        logger.info("[PRICE] product=%s category=%s(source=%s) material=%s size=%s "
                    "cost=%s complexity=%s confidence=%s",
                    product.id, detected["category"], detected["category_source"],
                    detected["material"], detected["size_bucket"],
                    detected["material_cost_inr"], detected["complexity_score"],
                    detected["confidence"])
        # Persist the detected category/material onto the product.
        product.category = product.category or detected["category"].replace("_", " ")
        if not product.material:
            product.material = detected["material"]

        if detected["confidence"] == "low":
            # No reliable signal to price from. Do NOT emit the cheapest-category
            # default as if it were a recommendation (that is the ₹260 bug).
            # Leave price unset so the review screen asks the artisan to set one.
            product.suggested_price = None
            product.price_low = None
            product.price_high = None
            product.price_reasoning = (
                "Could not auto-estimate a price — the product details didn't "
                "identify a known craft category. Please set your price."
            )
            logger.warning("[PRICE] product=%s LOW confidence — leaving price unset "
                           "(no fake default).", product.id)
        else:
            price_res = pricing.suggest(
                category=detected["category"],
                material=detected["material"],
                size_bucket=detected["size_bucket"],
                complexity_score=detected["complexity_score"],
                material_cost_inr=detected["material_cost_inr"],
                description=product.short_description or product.title or "",
            )
            product.suggested_price = price_res["price"]
            product.price_low = price_res["low"]
            product.price_high = price_res["high"]
            product.price_reasoning = price_res["reasoning"]
            if product.price is None:
                product.price = price_res["price"]
            logger.info("[PRICE] product=%s suggested=Rs%s (range %s-%s)",
                        product.id, price_res["price"], price_res["low"], price_res["high"])
        _set_step(job, "price", "done"); db.commit()

        # 5. Assemble ---------------------------------------------------------
        _set_step(job, "assemble", "running"); db.commit()
        product.status = ProductStatus.READY_FOR_REVIEW
        _set_step(job, "assemble", "done"); db.commit()

        job.status = JobStatus.SUCCEEDED
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("AI pipeline job failed")
        db.rollback()
        job = db.get(Job, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            prod = db.get(Product, job.product_id)
            if prod:
                prod.status = ProductStatus.FAILED
            db.commit()
    finally:
        db.close()


def _run_publish(job_id: str, channels: list[str]) -> None:
    db: Session = SessionLocal()
    try:
        job = db.get(Job, job_id)
        product = db.get(Product, job.product_id)
        job.status = JobStatus.RUNNING
        _set_step(job, "publish", "running")
        db.commit()

        canonical = _canonical_dict(product, db)
        any_live = False

        for ch in channels:
            row = _get_or_create_channel(db, product.id, ch)
            row.status = ChannelStatus.PROCESSING
            db.commit()

            adapter = get_adapter(ch)
            if adapter is None:
                row.status = ChannelStatus.FAILED
                row.error_reason = f"Unknown channel '{ch}'"
                db.commit()
                continue

            # Demo mode: no real credentials -> simulate a successful listing so
            # the end-to-end flow is demonstrable. Real creds always win.
            from core.config import settings as _settings
            if not adapter.enabled and _settings.demo_mode:
                ext = _demo_listing_id(product.id)
                row.status = ChannelStatus.LIVE
                row.external_product_id = ext
                row.listing_url = f"/demo/{ch}/product/{ext}"
                row.error_reason = None
                any_live = True
                db.commit()
                continue

            # Each channel is independent: a failure here never aborts the loop.
            try:
                res = adapter.publish(canonical)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Publish to %s crashed", ch)
                row.status = ChannelStatus.FAILED
                row.error_reason = f"Unexpected error: {exc}"
                row.retry_count += 1
                db.commit()
                continue

            if res.ok:
                row.status = ChannelStatus.LIVE
                row.external_product_id = res.external_product_id
                row.listing_url = res.listing_url
                row.error_reason = None
                any_live = True
            else:
                # Missing-config errors are "needs attention", not hard failures.
                needs_attention = adapter.enabled is False
                row.status = (ChannelStatus.NEEDS_ATTENTION if needs_attention
                              else ChannelStatus.FAILED)
                row.error_reason = res.error
                row.retry_count += 1
            db.commit()

        product.status = ProductStatus.LIVE if any_live else ProductStatus.READY_FOR_REVIEW
        _set_step(job, "publish", "done")
        job.status = JobStatus.SUCCEEDED
        db.commit()

        # Instagram is another channel consuming the canonical product — kick off
        # the platform-level content pipeline in the background (spec: automation).
        start_instagram(product.id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Publish job failed")
        db.rollback()
        job = db.get(Job, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            db.commit()
    finally:
        db.close()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _demo_listing_id(product_id: str) -> str:
    """Deterministic, realistic-looking listing id shared across channels."""
    n = int(product_id[:8], 16) % 100000
    return f"ART-{n:05d}"


def _get_or_create_channel(db: Session, product_id: str, channel: str) -> ProductChannel:
    row = (db.query(ProductChannel)
             .filter_by(product_id=product_id, channel=channel).first())
    if row is None:
        row = ProductChannel(product_id=product_id, channel=channel,
                             status=ChannelStatus.PENDING)
        db.add(row)
        db.commit()
    return row


def _canonical_dict(product: Product, db: Session) -> dict[str, Any]:
    artisan = product.artisan
    return {
        "id": product.id,
        "title": product.title,
        "short_description": product.short_description,
        "long_description": product.long_description,
        "highlights": product.highlights,
        "keywords": product.keywords,
        "category": product.category,
        "material": product.material,
        "dimensions": product.dimensions,
        "price": product.price,
        "suggested_price": product.suggested_price,
        "currency": product.currency,
        "original_images": product.original_images,
        "enhanced_images": product.enhanced_images,
        "business_name": getattr(artisan, "business_name", None),
    }


def _story_from(result: dict[str, Any]) -> str | None:
    return result.get("story")
