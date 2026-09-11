"""
Sarvam AI speech-to-text service (real Indian-language STT + translation).

Uses Sarvam's ``speech-to-text-translate`` endpoint: it transcribes an artisan's
voice note in any supported Indian language AND returns English text in one
call, plus the detected language. That English text feeds straight into the
description generator and pricing inference — so voice input works without a GPU
or the heavier artisan_ai pipeline.

Docs: https://docs.sarvam.ai
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

_TRANSLATE_URL = "https://api.sarvam.ai/speech-to-text-translate"
_STT_URL = "https://api.sarvam.ai/speech-to-text"
_TEXT_TRANSLATE_URL = "https://api.sarvam.ai/translate"
_TTS_URL = "https://api.sarvam.ai/text-to-speech"

_BCP47 = {
    "hi": "hi-IN", "pa": "pa-IN", "en": "en-IN", "ta": "ta-IN", "te": "te-IN",
    "bn": "bn-IN", "mr": "mr-IN", "gu": "gu-IN", "kn": "kn-IN", "ml": "ml-IN",
    "or": "od-IN",
}

_LANG_NAMES = {
    "hi": "Hindi", "pa": "Punjabi", "ta": "Tamil", "te": "Telugu",
    "bn": "Bengali", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada",
    "ml": "Malayalam", "or": "Odia", "en": "English", "ur": "Urdu", "as": "Assamese",
}


class SarvamService:
    def __init__(self) -> None:
        self.api_key = settings.sarvam_api_key.strip()
        self.model = settings.sarvam_stt_model

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def transcribe_translate(self, audio_path: str) -> dict[str, Any] | None:
        """Return {text, transcript_original, language_code, language_name} or None."""
        if not self.available:
            return None
        if not os.path.isfile(audio_path):
            logger.warning("Sarvam: audio file missing: %s", audio_path)
            return None

        try:
            with open(audio_path, "rb") as fh:
                resp = httpx.post(
                    _TRANSLATE_URL,
                    headers={"api-subscription-key": self.api_key},
                    files={"file": (os.path.basename(audio_path), fh, "audio/wav")},
                    data={"model": self.model},
                    timeout=90.0,
                )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Sarvam HTTP %s: %s", exc.response.status_code, exc.response.text[:300])
            return None
        except Exception:  # noqa: BLE001
            logger.exception("Sarvam request failed")
            return None

        data = resp.json()
        english = (data.get("transcript") or "").strip()
        if not english:
            return None
        bcp47 = data.get("language_code") or ""
        iso = bcp47.split("-")[0] if bcp47 else "en"
        return {
            "text": english,
            "language_code": iso,
            "language_name": _LANG_NAMES.get(iso, iso.title()),
            "language_probability": data.get("language_probability"),
        }


    # ── Spoken-language transcription (for the review step) ──────────────────
    def transcribe(self, audio_path: str, language: str = "unknown") -> dict[str, Any] | None:
        """Transcribe in the SPOKEN language (no translation). For the review card."""
        if not self.available or not os.path.isfile(audio_path):
            return None
        lang = _BCP47.get(language, "unknown")
        try:
            with open(audio_path, "rb") as fh:
                resp = httpx.post(
                    _STT_URL,
                    headers={"api-subscription-key": self.api_key},
                    files={"file": (os.path.basename(audio_path), fh, "audio/wav")},
                    data={"model": "saarika:v2.5", "language_code": lang},
                    timeout=90.0,
                )
            resp.raise_for_status()
        except Exception:  # noqa: BLE001
            logger.exception("Sarvam transcribe failed")
            return None
        data = resp.json()
        text = (data.get("transcript") or "").strip()
        if not text:
            return None
        bcp = data.get("language_code") or lang
        iso = bcp.split("-")[0] if bcp and bcp != "unknown" else (language or "en")
        return {"text": text, "language_code": iso,
                "language_name": _LANG_NAMES.get(iso, iso.title())}

    # ── Text translation (spoken-language transcript -> English listing) ─────
    def translate_text(self, text: str, source: str, target: str = "en") -> str | None:
        if not self.available or not text:
            return None
        if source == target:
            return text
        try:
            resp = httpx.post(
                _TEXT_TRANSLATE_URL,
                headers={"api-subscription-key": self.api_key},
                json={
                    "input": text,
                    "source_language_code": _BCP47.get(source, "en-IN"),
                    "target_language_code": _BCP47.get(target, "en-IN"),
                },
                timeout=45.0,
            )
            resp.raise_for_status()
            return (resp.json().get("translated_text") or "").strip() or None
        except Exception:  # noqa: BLE001
            logger.exception("Sarvam text translate failed")
            return None

    # ── Text-to-speech (speaker buttons) ─────────────────────────────────────
    def tts(self, text: str, language: str = "en") -> str | None:
        """Return base64 WAV audio for the given text in the given language."""
        if not self.available or not text:
            return None
        try:
            resp = httpx.post(
                _TTS_URL,
                headers={"api-subscription-key": self.api_key},
                json={
                    "text": text[:1500],
                    "target_language_code": _BCP47.get(language, "en-IN"),
                    "model": "bulbul:v3",
                },
                timeout=45.0,
            )
            resp.raise_for_status()
            audios = resp.json().get("audios") or []
            return audios[0] if audios else None
        except Exception:  # noqa: BLE001
            logger.exception("Sarvam TTS failed")
            return None


_sarvam: SarvamService | None = None


def get_sarvam_service() -> SarvamService:
    global _sarvam
    if _sarvam is None:
        _sarvam = SarvamService()
    return _sarvam
