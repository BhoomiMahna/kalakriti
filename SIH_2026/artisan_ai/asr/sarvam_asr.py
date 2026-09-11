"""
artisan_ai.asr.sarvam_asr
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sarvam AI Speech-to-Text ASR provider.

Uses the Sarvam AI REST API with the ``saaras:v3`` model.
Simple multipart file upload — no two-step pipeline config needed.

API Reference
-------------
- Endpoint: ``POST https://api.sarvam.ai/speech-to-text``
- Auth: ``api-subscription-key`` header
- Input: multipart/form-data with WAV file
- Response: ``{"transcript": "...", "language_code": "hi-IN"}``

Docs: https://docs.sarvam.ai
"""

from __future__ import annotations

import logging
from typing import Any

from artisan_ai.asr.base import ASRProvider, TranscriptResult
from artisan_ai.config import LANGUAGE_MAP

logger = logging.getLogger(__name__)

# Sarvam uses BCP-47 codes (e.g. "hi-IN"), our pipeline uses ISO 639-1 ("hi").
# Map BCP-47 -> ISO 639-1
_BCP47_TO_ISO: dict[str, str] = {
    "hi-IN": "hi",
    "pa-IN": "pa",
    "ta-IN": "ta",
    "te-IN": "te",
    "bn-IN": "bn",
    "mr-IN": "mr",
    "gu-IN": "gu",
    "kn-IN": "kn",
    "ml-IN": "ml",
    "or-IN": "or",
    "en-IN": "en",
    "ur-IN": "ur",
    "as-IN": "as",
    "sa-IN": "sa",
    "sd-IN": "sd",
}

# Reverse: ISO 639-1 -> BCP-47 (for API requests)
_ISO_TO_BCP47: dict[str, str] = {v: k for k, v in _BCP47_TO_ISO.items()}

_SARVAM_API_URL = "https://api.sarvam.ai/speech-to-text"


class SarvamASR(ASRProvider):
    """ASR provider backed by Sarvam AI (saaras:v3 model).

    Parameters
    ----------
    config:
        ``Config`` instance providing Sarvam credentials.
    source_language:
        ISO 639-1 code of expected language (e.g. ``"pa"``).
        If ``"auto"`` or ``None``, sends ``"unknown"`` to Sarvam
        for automatic language detection.
    model:
        Sarvam model name. Defaults to ``"saaras:v3"``.
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        config: Any = None,
        source_language: str | None = None,
        model: str = "saaras:v3",
        timeout: int = 60,
    ) -> None:
        if config is None:
            from artisan_ai.config import Config
            config = Config()

        self._api_key = config.sarvam_api_key
        self._source_language = source_language
        self._model = model
        self._timeout = timeout

    def transcribe(self, audio_path: str) -> TranscriptResult:
        """Transcribe *audio_path* using Sarvam AI Speech-to-Text.

        Parameters
        ----------
        audio_path:
            Path to a preprocessed 16 kHz mono WAV file.

        Returns
        -------
        TranscriptResult
        """
        import requests

        self._validate_credentials()

        logger.info("Sending audio to Sarvam AI ASR ...")

        # Determine language code for the API
        if (
            self._source_language
            and self._source_language not in ("auto", "unknown")
        ):
            lang_bcp47 = _ISO_TO_BCP47.get(
                self._source_language,
                f"{self._source_language}-IN",
            )
        else:
            lang_bcp47 = "unknown"

        # Multipart file upload
        import os
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with open(audio_path, "rb") as f:
            files = {
                "file": (os.path.basename(audio_path), f, "audio/wav"),
            }
            data = {
                "model": self._model,
                "language_code": lang_bcp47,
                "with_timestamps": "false",
            }
            headers = {
                "api-subscription-key": self._api_key,
            }

            try:
                resp = requests.post(
                    _SARVAM_API_URL,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=self._timeout,
                )
                resp.raise_for_status()
            except requests.exceptions.Timeout:
                raise RuntimeError(
                    "Sarvam AI ASR request timed out. "
                    "Audio may be too long (max 30s for sync API)."
                )
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code
                body = exc.response.text[:300]
                if status == 401 or status == 403:
                    raise RuntimeError(
                        "Sarvam AI authentication failed. "
                        "Check your SARVAM_API_KEY."
                    ) from exc
                raise RuntimeError(
                    f"Sarvam AI ASR failed (HTTP {status}): {body}"
                ) from exc
            except requests.exceptions.ConnectionError as exc:
                raise RuntimeError(
                    "Could not connect to Sarvam AI. Check your network."
                ) from exc

        result = resp.json()

        # Extract transcript
        transcript = result.get("transcript", "").strip()
        if not transcript:
            raise RuntimeError(
                f"Sarvam AI returned empty transcript. Response: {result}"
            )

        # Extract detected language (BCP-47 -> ISO 639-1)
        detected_bcp47 = result.get("language_code") or lang_bcp47
        if detected_bcp47 == "unknown":
            lang_code = self._source_language or "und"
        else:
            lang_code = _BCP47_TO_ISO.get(detected_bcp47, detected_bcp47.split("-")[0])

        lang_name = LANGUAGE_MAP.get(lang_code, lang_code.title())

        logger.info(
            "Sarvam AI ASR completed: %s (%s), %d chars.",
            lang_name, lang_code, len(transcript),
        )

        return TranscriptResult(
            transcript=transcript,
            language_code=lang_code,
            language_name=lang_name,
            confidence=None,
            model_name=f"sarvam-{self._model}",
        )

    def _validate_credentials(self) -> None:
        """Raise if Sarvam API key is missing."""
        if not self._api_key:
            raise EnvironmentError(
                "Missing SARVAM_API_KEY.\n"
                "Set it in your .env file or environment.\n"
                "Get your key at https://console.sarvam.ai"
            )
