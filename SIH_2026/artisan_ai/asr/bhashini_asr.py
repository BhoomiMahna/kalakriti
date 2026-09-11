"""
artisan_ai.asr.bhashini_asr
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

BHASHINI Speech-to-Text ASR provider.

Uses the official BHASHINI/ULCA API (two-step flow):
  1. Pipeline config  -> get serviceId + callbackUrl + inferenceApiKey
  2. Inference request -> send base64 audio, receive transcript

The pipeline configuration is cached so repeated calls do not
re-fetch the service ID.

Credentials are read from the ``Config`` object (which reads ``.env``).
API keys are NEVER logged.

Reference
---------
- https://bhashini.gov.in
- https://github.com/bhashini-ai/bhashini-api-examples
"""

from __future__ import annotations

import base64
import logging
from typing import Any

from artisan_ai.asr.base import ASRProvider, TranscriptResult
from artisan_ai.config import LANGUAGE_MAP

logger = logging.getLogger(__name__)

# ── BHASHINI language name -> ISO 639-1 ────────────────────────────────────────
# BHASHINI pipeline config returns full language names; we need ISO codes.
_BHASHINI_NAME_TO_ISO: dict[str, str] = {
    "Hindi": "hi",
    "Punjabi": "pa",
    "Tamil": "ta",
    "Telugu": "te",
    "Bengali": "bn",
    "Marathi": "mr",
    "Gujarati": "gu",
    "Kannada": "kn",
    "Malayalam": "ml",
    "Odia": "or",
    "English": "en",
    "Urdu": "ur",
    "Assamese": "as",
    "Sanskrit": "sa",
    "Sindhi": "sd",
}

# ISO 639-1 -> BHASHINI language name (for API requests)
_ISO_TO_BHASHINI_NAME: dict[str, str] = {v: k for k, v in _BHASHINI_NAME_TO_ISO.items()}

# ULCA pipeline config endpoint
_ULCA_CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"


class BhashiniASR(ASRProvider):
    """ASR provider backed by BHASHINI Speech-to-Text API.

    Parameters
    ----------
    config:
        ``Config`` instance providing BHASHINI credentials.
    source_language:
        ISO 639-1 code of the expected source language (e.g. ``"pa"``).
        If ``None``, defaults to ``"hi"`` (Hindi).  The BHASHINI ASR
        model is language-specific, so this must be set correctly.
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        config: Any = None,
        source_language: str = "hi",
        timeout: int = 60,
    ) -> None:
        if config is None:
            from artisan_ai.config import Config
            config = Config()

        self._user_id = config.bhashini_user_id
        self._api_key = config.bhashini_api_key
        self._pipeline_id = config.bhashini_pipeline_id
        self._source_language = source_language
        self._timeout = timeout

        # Cached pipeline config (populated on first transcribe call)
        self._service_id: str | None = None
        self._callback_url: str | None = None
        self._inference_api_key: str | None = None

    # ── Pipeline config (step 1) ───────────────────────────────────────────────

    def _fetch_pipeline_config(self) -> None:
        """Call ULCA getModelsPipeline to obtain serviceId and callbackUrl."""
        if self._service_id is not None:
            return  # Already cached

        self._validate_credentials()

        import requests  # type: ignore[import]

        logger.info("Fetching BHASHINI pipeline config ...")

        payload = {
            "pipelineTasks": [
                {"taskType": "asr"}
            ],
            "pipelineRequestConfig": {
                "pipelineId": self._pipeline_id,
            },
        }
        headers = {
            "userID": self._user_id,
            "ulcaApiKey": self._api_key,
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                _ULCA_CONFIG_URL,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError(
                "BHASHINI pipeline config request timed out. "
                "Check your network connection."
            )
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(
                f"BHASHINI pipeline config failed (HTTP {exc.response.status_code}). "
                f"Check your BHASHINI_USER_ID and BHASHINI_API_KEY."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                "Could not connect to BHASHINI API. Check your network."
            ) from exc

        data = resp.json()

        # Extract callback URL and inference key from pipelineInferenceAPIEndPoint
        try:
            endpoint_info = data["pipelineInferenceAPIEndPoint"]
            self._callback_url = endpoint_info["callbackUrl"]
            self._inference_api_key = (
                endpoint_info.get("inferenceApiKey", {}).get("value", "")
            )
        except (KeyError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected BHASHINI pipeline config response format: {exc}\n"
                f"Response: {data}"
            ) from exc

        # Extract serviceId from pipelineResponseConfig
        try:
            task_configs = data.get("pipelineResponseConfig", [])
            for task_config in task_configs:
                if task_config.get("taskType") == "asr":
                    configs = task_config.get("config", [])
                    if configs:
                        self._service_id = configs[0].get("serviceId", "")
                        break
            if not self._service_id:
                raise ValueError("No ASR serviceId found")
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Could not extract ASR serviceId from BHASHINI response: {exc}\n"
                f"Response: {data}"
            ) from exc

        logger.info(
            "BHASHINI pipeline config obtained (serviceId=%s...)",
            self._service_id[:12] if self._service_id else "?",
        )

    # ── Inference (step 2) ─────────────────────────────────────────────────────

    def transcribe(self, audio_path: str) -> TranscriptResult:
        """Transcribe *audio_path* using BHASHINI Speech-to-Text API.

        Parameters
        ----------
        audio_path:
            Path to a preprocessed 16 kHz mono WAV file.

        Returns
        -------
        TranscriptResult
            The original-language transcript and detected language metadata.
        """
        import requests  # type: ignore[import]

        self._fetch_pipeline_config()

        logger.info("Sending audio to BHASHINI ASR ...")

        # Read and base64-encode the audio file
        audio_b64 = self._encode_audio(audio_path)

        # Build inference payload
        src_lang = self._source_language
        payload = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {
                            "sourceLanguage": src_lang,
                        },
                        "serviceId": self._service_id,
                        "audioFormat": "wav",
                        "samplingRate": 16000,
                    },
                }
            ],
            "inputData": {
                "audio": [
                    {"audioContent": audio_b64}
                ],
            },
        }

        headers = {
            "Content-Type": "application/json",
        }
        if self._inference_api_key:
            headers["Authorization"] = self._inference_api_key

        try:
            resp = requests.post(
                self._callback_url,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError(
                "BHASHINI ASR inference request timed out. "
                "The audio file may be too large or the service may be busy."
            )
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(
                f"BHASHINI ASR inference failed (HTTP {exc.response.status_code}). "
                f"Response: {exc.response.text[:200]}"
            ) from exc

        data = resp.json()

        # Parse transcript from response
        transcript = self._extract_transcript(data)
        lang_name = LANGUAGE_MAP.get(src_lang, src_lang.title())

        logger.info("BHASHINI ASR completed (%d chars).", len(transcript))

        return TranscriptResult(
            transcript=transcript,
            language_code=src_lang,
            language_name=lang_name,
            confidence=None,
            model_name="bhashini-asr",
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _validate_credentials(self) -> None:
        """Raise if BHASHINI credentials are missing."""
        missing = []
        if not self._user_id:
            missing.append("BHASHINI_USER_ID")
        if not self._api_key:
            missing.append("BHASHINI_API_KEY")
        if missing:
            raise EnvironmentError(
                f"Missing BHASHINI credentials: {', '.join(missing)}.\n"
                "Set them in your .env file or environment variables.\n"
                "Register at https://bhashini.gov.in to obtain credentials."
            )

    @staticmethod
    def _encode_audio(audio_path: str) -> str:
        """Read a WAV file and return its base64-encoded content."""
        import os
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        if len(audio_bytes) == 0:
            raise ValueError(f"Audio file is empty: {audio_path}")

        return base64.b64encode(audio_bytes).decode("utf-8")

    @staticmethod
    def _extract_transcript(data: dict) -> str:
        """Extract transcript text from BHASHINI inference response."""
        try:
            pipeline_response = data.get("pipelineResponse", [])
            for task_response in pipeline_response:
                if task_response.get("taskType") == "asr":
                    output = task_response.get("output", [])
                    if output:
                        return output[0].get("source", "").strip()

            # Fallback: try flat output structure
            output = data.get("output", [])
            if output:
                return output[0].get("source", "").strip()

        except (KeyError, IndexError, TypeError):
            pass

        raise RuntimeError(
            f"Could not extract transcript from BHASHINI response.\n"
            f"Response keys: {list(data.keys())}\n"
            f"Full response: {str(data)[:500]}"
        )
