"""Platform admin: health, integration status, failed jobs (spec §3, §22)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from marketplace.registry import channel_statuses
from models import Job, JobStatus, Product
from core.config import settings
from services.ai_service import get_ai_service
from services.image_service import get_photoshoot_service
from services.pricing_service import get_pricing_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "demo_mode": settings.demo_mode,
        "ai_pipeline": get_ai_service().mode,
        "image_photoshoot": get_photoshoot_service().mode,
        "pricing_model_loaded": get_pricing_service().available,
        "marketplaces": channel_statuses(),
        "instagram": _instagram_mode(),
    }


def _instagram_mode() -> dict:
    try:
        from integrations.instagram import service as ig
        return ig.mode_info()
    except Exception:  # noqa: BLE001
        return {"enabled": False}


@router.get("/image/info")
def image_info() -> dict:
    """Developer/admin view of the photoshoot config — NO secrets/keys.

    Lets you verify the mode and the EXACT prompts sent to the image model.
    """
    from services.image_service import build_prompt
    from services.demo_photoshoot import get_demo_registry

    svc = get_photoshoot_service()
    if svc.generative:
        mode = "REAL_AI"
    elif svc.mode == "isolate":
        mode = "REAL_AI_ISOLATION"
    else:
        mode = "UNAVAILABLE"
    prompts = {
        s: build_prompt(s, category="bottle", material="glass, decorated",
                        description="handmade decorated glass bottle")
        for s in ("hero", "lifestyle", "detail")
    }
    return {
        "image_demo_mode": settings.image_demo_mode,
        "demo_source_count": len(get_demo_registry().source_hashes),
        "real_ai_mode": mode,
        "provider": svc.provider or None,
        "model": settings.gemini_image_model if svc.provider == "gemini" else None,
        "has_gemini_key": bool(settings.gemini_api_key or settings.google_api_key),
        "prompts": prompts,
    }


@router.get("/image/selftest")
def image_selftest() -> dict:
    """Run ONE real generative image request from the backend and report the
    outcome — safely (never returns or logs the API key). Isolates a genuine
    Gemini API failure (ok=false + error) from a downstream validation failure
    (ok=true here, but shots still fail in the pipeline)."""
    import io
    import os
    from PIL import Image
    from services.image_service import get_photoshoot_service, build_prompt

    svc = get_photoshoot_service()
    out: dict = {
        "provider": svc.provider or None,
        "generative": svc.generative,
        "model": settings.gemini_image_model if svc.generative else None,
        "gemini_key_configured": bool(settings.gemini_api_key or settings.google_api_key),
    }
    if not svc.generative:
        out["note"] = "No generative provider configured — using isolation preview."
        return out

    img = Image.new("RGB", (640, 640), (170, 140, 95))
    prompt = build_prompt("hero", "bowl", "brass", "handmade decorated brass bowl")
    dest = os.path.join(settings.storage_dir, "_selftest_gemini.jpg")
    try:
        svc._provider_generate(prompt, img, dest)   # raw generate, bypasses validation
        out["ok"] = True
        out["output_bytes"] = os.path.getsize(dest) if os.path.exists(dest) else 0
    except Exception as exc:  # noqa: BLE001
        logger.exception("[IMAGE] selftest generation failed")
        out["ok"] = False
        out["error"] = str(exc)[:600]
    return out


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    return {
        "products": db.query(Product).count(),
        "failed_jobs": db.query(Job).filter(Job.status == JobStatus.FAILED).count(),
        "running_jobs": db.query(Job).filter(Job.status == JobStatus.RUNNING).count(),
    }
