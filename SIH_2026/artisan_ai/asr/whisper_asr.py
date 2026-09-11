"""
artisan_ai.asr.whisper_asr
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Whisper-based ASR provider using faster-whisper.

faster-whisper uses CTranslate2 and is significantly faster than
openai-whisper for CPU inference.

Supported model sizes:
    tiny, base, small, medium, large-v2, large-v3
"""

from __future__ import annotations

import logging
from typing import Any

from artisan_ai.asr.base import ASRProvider, TranscriptResult
from artisan_ai.config import LANGUAGE_MAP

logger = logging.getLogger(__name__)


class WhisperASR(ASRProvider):
    """ASR provider backed by faster-whisper.

    Parameters
    ----------
    model_size:
        Whisper model variant.
    device:
        ``"cpu"`` or ``"cuda"``.
    language:
        Optional ISO 639-1 language code, e.g. ``"pa"`` for Punjabi.
        If None, Whisper automatically detects the language.
    compute_type:
        faster-whisper computation type. ``"int8"`` is recommended
        for CPU inference.
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        language: str | None = None,
        compute_type: str | None = None,
        use_transformers: bool = False,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.language = language
        self.use_transformers = use_transformers

        # INT8 is much faster and lighter on CPU.
        if compute_type is None:
            self.compute_type = "int8" if device == "cpu" else "float16"
        else:
            self.compute_type = compute_type

        self._model: Any = None
        self._backend = ""

    # ── Lazy model loading ────────────────────────────────────────────────────

    def _load_model(self) -> None:
        if self._model is not None:
            return

        if self.use_transformers:
            self._load_transformers_whisper()
        else:
            self._load_faster_whisper()

    def _load_faster_whisper(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ImportError(
                "faster-whisper is not installed. "
                "Run: pip install faster-whisper"
            ) from exc

        logger.info(
            "Loading faster-whisper (%s) on %s with %s ...",
            self.model_size,
            self.device,
            self.compute_type,
        )

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )

        self._backend = "faster-whisper"

        logger.info("faster-whisper model loaded.")

    def _load_transformers_whisper(self) -> None:
        from transformers import pipeline as hf_pipeline

        model_id = f"openai/whisper-{self.model_size}"

        logger.info(
            "Loading Whisper (%s) via transformers on %s ...",
            model_id,
            self.device,
        )

        # transformers uses device index:
        # -1 = CPU
        #  0 = first CUDA GPU
        pipeline_device = -1 if self.device == "cpu" else 0

        self._model = hf_pipeline(
            "automatic-speech-recognition",
            model=model_id,
            device=pipeline_device,
            return_timestamps=True,
        )

        self._backend = "transformers"

        logger.info("Whisper (transformers) model loaded.")

    # ── Transcription ─────────────────────────────────────────────────────────

    def transcribe(self, audio_path: str) -> TranscriptResult:
        """Transcribe audio and return the original-language transcript."""

        self._load_model()

        if self._backend == "faster-whisper":
            return self._transcribe_faster_whisper(audio_path)

        return self._transcribe_transformers(audio_path)

    def _transcribe_faster_whisper(
        self,
        audio_path: str,
    ) -> TranscriptResult:

        logger.info("Transcribing (faster-whisper) ...")

        transcribe_kwargs: dict[str, Any] = {
            "task": "transcribe",
            "beam_size": 1,
            "vad_filter": True,
        }

        if self.language:
            transcribe_kwargs["language"] = self.language

        segments, info = self._model.transcribe(
            audio_path,
            **transcribe_kwargs,
        )

        # faster-whisper returns a generator, so actually consume it.
        segment_list = list(segments)

        text = " ".join(
            segment.text.strip()
            for segment in segment_list
            if segment.text.strip()
        ).strip()

        lang_code = getattr(info, "language", None) or self.language or "und"

        lang_name = LANGUAGE_MAP.get(
            lang_code,
            lang_code.title(),
        )

        # faster-whisper provides probability for detected language.
        confidence = getattr(
            info,
            "language_probability",
            None,
        )

        if confidence is not None:
            confidence = round(float(confidence), 4)

        logger.info(
            "Transcription complete: language=%s, confidence=%s",
            lang_code,
            confidence,
        )

        return TranscriptResult(
            transcript=text,
            language_code=lang_code,
            language_name=lang_name,
            confidence=confidence,
            model_name=f"faster-whisper-{self.model_size}",
        )

    def _transcribe_transformers(
        self,
        audio_path: str,
    ) -> TranscriptResult:

        logger.info("Transcribing (transformers pipeline) ...")

        generate_kwargs: dict[str, Any] = {
            "task": "transcribe",
        }

        if self.language:
            generate_kwargs["language"] = self.language

        result = self._model(
            audio_path,
            generate_kwargs=generate_kwargs,
        )

        text = result["text"].strip()

        lang_code = self.language or "und"

        chunks = result.get("chunks", [])

        for chunk in chunks:
            if hasattr(chunk, "language"):
                lang_code = chunk.language
                break

        lang_name = LANGUAGE_MAP.get(
            lang_code,
            lang_code.title(),
        )

        return TranscriptResult(
            transcript=text,
            language_code=lang_code,
            language_name=lang_name,
            confidence=None,
            model_name=f"openai/whisper-{self.model_size}",
        )