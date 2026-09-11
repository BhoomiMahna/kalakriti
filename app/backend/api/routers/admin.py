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


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    return {
        "products": db.query(Product).count(),
        "failed_jobs": db.query(Job).filter(Job.status == JobStatus.FAILED).count(),
        "running_jobs": db.query(Job).filter(Job.status == JobStatus.RUNNING).count(),
    }
