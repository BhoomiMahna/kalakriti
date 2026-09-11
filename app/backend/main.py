"""
Artisan Platform — FastAPI application entrypoint.

Run (from app/backend):

    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import admin, artisans, auth, instagram, products, public, voice
from core.config import settings
from db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("artisan_platform")

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
    logger.info("Artisan Platform API ready (env=%s)", settings.environment)


# Serve uploaded + enhanced media.
app.mount("/media", StaticFiles(directory=settings.storage_dir), name="media")

app.include_router(auth.router, prefix="/api")
app.include_router(artisans.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(instagram.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}
