"""Voice endpoints: spoken-language transcription (review step) + text-to-speech."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from api.deps import get_current_artisan
from core.config import settings
from models import Artisan
from services.sarvam_service import get_sarvam_service

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
    with dest.open("wb") as fh:
        fh.write(audio.file.read())

    sarvam = get_sarvam_service()
    if not sarvam.available:
        # No STT available — return empty so the UI falls back to typing.
        return {"transcript": "", "language_code": language, "audio_url": f"/media/{name}",
                "stt_available": False}

    res = sarvam.transcribe(str(dest), language=language)
    if not res:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            "Could not understand the audio. Please try again.")
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
    audio_b64 = get_sarvam_service().tts(payload.text, payload.language)
    if not audio_b64:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "TTS unavailable")
    return {"audio": audio_b64, "mime": "audio/wav"}
