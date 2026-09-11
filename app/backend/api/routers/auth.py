"""OTP-based phone authentication (spec §4.1)."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.config import settings
from core.security import create_access_token, hash_otp, verify_otp
from db.session import get_db
from models import OTP, Artisan
from schemas import ArtisanOut, OTPRequest, OTPRequestResponse, OTPVerify, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_OTP_ATTEMPTS = 5


@router.post("/request-otp", response_model=OTPRequestResponse)
def request_otp(payload: OTPRequest, db: Session = Depends(get_db)) -> OTPRequestResponse:
    code = f"{random.randint(0, 999999):06d}"
    otp = OTP(
        phone=payload.phone,
        code_hash=hash_otp(code),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.otp_expiry_seconds),
    )
    db.add(otp)
    db.commit()

    # In production an SMS provider (e.g. MSG91 / Twilio) sends the code.
    # In dev mode we return it so the flow is testable without a gateway.
    return OTPRequestResponse(
        sent=True,
        message="OTP sent to your phone." if not settings.otp_dev_mode
                else "OTP generated (dev mode).",
        dev_otp=code if settings.otp_dev_mode else None,
    )


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp_endpoint(payload: OTPVerify, db: Session = Depends(get_db)) -> TokenResponse:
    otp = (
        db.query(OTP)
        .filter(OTP.phone == payload.phone, OTP.consumed.is_(False))
        .order_by(OTP.created_at.desc())
        .first()
    )
    if not otp:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Request an OTP first.")
    if otp.attempts >= MAX_OTP_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Request a new OTP.")
    if otp.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OTP expired. Request a new one.")

    otp.attempts += 1
    if not verify_otp(payload.code, otp.code_hash):
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect OTP.")

    otp.consumed = True
    db.commit()

    artisan = db.query(Artisan).filter(Artisan.phone == payload.phone).first()
    is_new = artisan is None
    if is_new:
        artisan = Artisan(phone=payload.phone)
        db.add(artisan)
        db.commit()
        db.refresh(artisan)

    token = create_access_token(artisan.id)
    out = ArtisanOut.model_validate(artisan)
    out.profile_completion = artisan.completion_pct()
    return TokenResponse(access_token=token, is_new=is_new, artisan=out)
