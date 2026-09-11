"""Voice endpoints: spoken-language transcription (review step) + text-to-speech."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from api.deps import get_current_artisan
from core.config import settings
from models import Artisan
from services.sarvam_service import get_sarvam_service

logger = logging.getLogger("voice")
router = APIRouter(tags=["voice"])

STORAGE = Path(settings.storage_dir)
STORAGE.mkdir(parents=True, exist_ok=True)


@router.post("/transcribe")
def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("unknown"),
    artisan: Artisan = Depends(get_current_artisan),
) -> dict:
    """Transcribe a voice note in the SPOKEN language for the review card."""
    ext = Path(audio.filename or "").suffix.lower() or ".wav"
    name = f"{uuid.uuid4().hex}{ext}"
    dest = STORAGE / name
    data = audio.file.read()
    with dest.open("wb") as fh:
        fh.write(data)
    logger.info("[STT] audio received: name=%s size=%dB mime=%s lang=%s",
                audio.filename, len(data), audio.content_type, language)

    sarvam = get_sarvam_service()
    if not sarvam.available:
        # No STT configured — return empty so the UI falls back to typing.
        logger.warning("[STT] SARVAM_API_KEY not configured on the server — "
                       "returning stt_available=false (empty transcript).")
        return {"transcript": "", "language_code": language, "audio_url": f"/media/{name}",
                "stt_available": False}

    if len(data) < 2000:
        logger.warning("[STT] audio very small (%dB) — likely silent/too short.", len(data))

    res = sarvam.transcribe(str(dest), language=language)
    if not res:
        logger.error("[STT] Sarvam returned no usable transcript (see sarvam logs above).")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            "Could not understand the audio. Please try again.")
    logger.info("[STT] transcript ok: lang=%s len=%d chars", res["language_code"], len(res["text"]))
    return {
        "transcript": res["text"],
        "language_code": res["language_code"],
        "language_name": res["language_name"],
        "audio_url": f"/media/{name}",
        "stt_available": True,
    }


class TTSRequest(BaseModel):
    text: str
    language: str = "en"


@router.post("/tts")
def text_to_speech(payload: TTSRequest) -> dict:
    """Return base64 WAV audio speaking the text in the given language.

    Public (no auth) so the pre-login language/login screens can speak too.
    """
    sarvam = get_sarvam_service()
    if not sarvam.available:
        logger.warning("[TTS] SARVAM_API_KEY not configured — the client will fall back to "
                       "the browser voice.")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "TTS not configured")
    audio_b64 = sarvam.tts(payload.text, payload.language)
    if not audio_b64:
        logger.error("[TTS] Sarvam returned no audio for lang=%s (see sarvam logs above).",
                     payload.language)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "TTS unavailable")
    logger.info("[TTS] audio ok: lang=%s bytes(b64)=%d", payload.language, len(audio_b64))
    return {"audio": audio_b64, "mime": "audio/wav"}
