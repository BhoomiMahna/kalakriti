"""
artisan_ai.translation.opus_mt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Helsinki-NLP opus-mt translation provider.

This is a fully pip-installable fallback translation provider.
It uses ``transformers`` + Helsinki-NLP's opus-mt models, which are
available for most Indian language → English pairs.

No extra repository cloning or setup is required.

Supported source languages
--------------------------
hi, pa, ta, te, bn, mr, gu, kn, ml, or, en

Model mapping
-------------
The model used is ``Helsinki-NLP/opus-mt-{src}-en`` where ``{src}`` is the
ISO 639-1 code.  For languages without a direct model, a multi-source
model (``Helsinki-NLP/opus-mt-mul-en``) is used as a fallback.
"""

from __future__ import annotations

import logging
from typing import Any

from artisan_ai.translation.base import TranslationProvider, TranslationResult

logger = logging.getLogger(__name__)

# Codes that have a dedicated opus-mt model
DIRECT_MODEL_LANGS: set[str] = {"hi", "ta", "te", "bn", "mr", "gu", "kn", "ml"}
FALLBACK_MODEL = "Helsinki-NLP/opus-mt-mul-en"


def _model_id(source_language: str) -> str:
    if source_language in DIRECT_MODEL_LANGS:
        return f"Helsinki-NLP/opus-mt-{source_language}-en"
    return FALLBACK_MODEL


class OpusMTProvider(TranslationProvider):
    """Translation provider backed by Helsinki-NLP opus-mt models.

    Parameters
    ----------
    device:
        ``"cpu"`` or ``"cuda"``.
    """

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._pipelines: dict[str, Any] = {}

    def _get_pipeline(self, source_language: str) -> Any:
        model_id = _model_id(source_language)
        if model_id not in self._pipelines:
            from transformers import pipeline as hf_pipeline  # type: ignore[import]

            logger.info("Loading opus-mt model: %s ...", model_id)
            self._pipelines[model_id] = hf_pipeline(
                "translation",
                model=model_id,
                device=self.device,
            )
            logger.info("Model loaded: %s", model_id)
        return self._pipelines[model_id], model_id

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str = "en",
    ) -> TranslationResult:
        """Translate *text* from *source_language* to English.

        Parameters
        ----------
        text:
            Source text.
        source_language:
            ISO 639-1 source language code.
        target_language:
            Ignored; opus-mt models here are all ``→ en``.
        """
        if not text.strip():
            return TranslationResult(
                translated_text="",
                source_language=source_language,
                target_language="en",
                model_name=FALLBACK_MODEL,
            )

        pipe, model_id = self._get_pipeline(source_language)
        logger.info("Translating via opus-mt '%s' ...", model_id)

        # opus-mt has a max token limit; split long texts
        chunks = self._chunk_text(text, max_chars=400)
        translated_chunks = []
        for chunk in chunks:
            result = pipe(chunk, max_length=512)
            translated_chunks.append(result[0]["translation_text"])

        translated_text = " ".join(translated_chunks).strip()
        logger.info("Translation complete (%d chars).", len(translated_text))

        return TranslationResult(
            translated_text=translated_text,
            source_language=source_language,
            target_language="en",
            model_name=model_id,
        )

    @staticmethod
    def _chunk_text(text: str, max_chars: int = 400) -> list[str]:
        """Split text into chunks of at most *max_chars* characters."""
        import re

        sentences = re.split(r"(?<=[।.!?])\s+", text)
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= max_chars:
                current = f"{current} {sentence}".strip()
            else:
                if current:
                    chunks.append(current)
                current = sentence
        if current:
            chunks.append(current)
        return chunks or [text]
