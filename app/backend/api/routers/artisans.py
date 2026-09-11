"""Artisan profile management (spec §4.1 — register once)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_current_artisan
from db.session import get_db
from marketplace.registry import channel_statuses
from models import Artisan
from schemas import ArtisanOut, ArtisanUpdate

router = APIRouter(prefix="/artisans", tags=["artisans"])


def _out(artisan: Artisan) -> ArtisanOut:
    out = ArtisanOut.model_validate(artisan)
    out.profile_completion = artisan.completion_pct()
    return out


@router.get("/me", response_model=ArtisanOut)
def get_me(artisan: Artisan = Depends(get_current_artisan)) -> ArtisanOut:
    return _out(artisan)


@router.patch("/me", response_model=ArtisanOut)
def update_me(
    payload: ArtisanUpdate,
    artisan: Artisan = Depends(get_current_artisan),
    db: Session = Depends(get_db),
) -> ArtisanOut:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(artisan, field, value)
    artisan.profile_complete = artisan.completion_pct() >= 80
    artisan.ready_to_sell = bool(artisan.name and artisan.craft_category and artisan.location)
    db.commit()
    db.refresh(artisan)
    return _out(artisan)


@router.get("/me/channels")
def my_channels(artisan: Artisan = Depends(get_current_artisan)) -> dict:
    """Marketplace connection status shown on the dashboard."""
    return {"channels": channel_statuses()}
