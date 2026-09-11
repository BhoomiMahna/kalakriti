"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from core.security import decode_access_token
from db.session import get_db
from models import Artisan


def get_current_artisan(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Artisan:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    artisan_id = decode_access_token(token)
    if not artisan_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    artisan = db.get(Artisan, artisan_id)
    if not artisan:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Artisan not found")
    return artisan
