"""
artisan_ai.language.detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Language detection for artisan speech recordings.

Strategy (in order of preference):
  1. Reuse the language code already reported by the ASR model
     (Whisper's language identification is state-of-the-art).
  2. Run ``langdetect`` on the transcript text as a fallback.
  3. Default to ``"und"`` (undetermined) if both fail.

The result is a :class:`LanguageResult` dataclass that is passed
downstream to the translation and follow-up question stages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from artisan_ai.config import LANGUAGE_MAP

logger = logging.getLogger(__name__)

# ── Indic-language-aware normalizations ──────────────────────────────────────
# langdetect sometimes returns codes that differ from Whisper's ISO 639-1 codes.
LANGDETECT_CODE_MAP: dict[str, str] = {
    "zh-cn": "zh",
    "zh-tw": "zh",
}


@dataclass
class LanguageResult:
    """Detected language metadata.

    Attributes
    ----------
    code:
        ISO 639-1 language code (e.g. ``"pa"`` for Punjabi).
    name:
        Human-readable language name (e.g. ``"Punjabi"``).
    confidence:
        Probability estimate (0–1) or ``None`` if unavailable.
    source:
        Which subsystem provided the result:
        ``"asr"`` | ``"langdetect"`` | ``"default"``.
    """

    code: str
    name: str
    confidence: float | None
    source: str


class LanguageDetector:
    """Determine the language of an artisan's recording.

    Parameters
    ----------
    use_asr_result:
        If ``True`` (default), accept the language code from the ASR stage
        without re-running detection.
    fallback_to_langdetect:
        If ``True`` (default), run ``langdetect`` when the ASR result is
        unavailable or reports ``"und"``.
    """

    UNDETERMINED = "und"

    def __init__(
        self,
        use_asr_result: bool = True,
        fallback_to_langdetect: bool = True,
    ) -> None:
        self.use_asr_result = use_asr_result
        self.fallback_to_langdetect = fallback_to_langdetect

    def detect(
        self,
        *,
        asr_language_code: str | None = None,
        asr_confidence: float | None = None,
        transcript_text: str | None = None,
    ) -> LanguageResult:
        """Detect or confirm the language of the artisan's recording.

        Parameters
        ----------
        asr_language_code:
            Language code reported by the ASR model (may be ``None`` or
            ``"und"``).
        asr_confidence:
            ASR model's language-detection confidence (may be ``None``).
        transcript_text:
            The raw transcript text; used by the ``langdetect`` fallback.

        Returns
        -------
        LanguageResult
        """
        # ── 1. Use ASR language id ────────────────────────────────────────────
        if (
            self.use_asr_result
            and asr_language_code
            and asr_language_code != self.UNDETERMINED
        ):
            lang_name = LANGUAGE_MAP.get(asr_language_code, asr_language_code.title())
            logger.info(
                "Language confirmed from ASR: %s (%s), confidence=%s",
                lang_name,
                asr_language_code,
                asr_confidence,
            )
            return LanguageResult(
                code=asr_language_code,
                name=lang_name,
                confidence=asr_confidence,
                source="asr",
            )

        # ── 2. langdetect fallback ────────────────────────────────────────────
        if self.fallback_to_langdetect and transcript_text:
            result = self._detect_with_langdetect(transcript_text)
            if result:
                return result

        # ── 3. Default: undetermined ──────────────────────────────────────────
        logger.warning(
            "Language detection failed; defaulting to 'und'. "
            "Downstream translation may not function correctly."
        )
        return LanguageResult(
            code=self.UNDETERMINED,
            name="Undetermined",
            confidence=None,
            source="default",
        )

    def _detect_with_langdetect(self, text: str) -> LanguageResult | None:
        try:
            from langdetect import DetectorFactory, detect_langs  # type: ignore[import]

            # Seed for reproducibility
            DetectorFactory.seed = 0
            detections = detect_langs(text)

            if not detections:
                return None

            top = detections[0]
            raw_code = LANGDETECT_CODE_MAP.get(top.lang, top.lang)
            lang_name = LANGUAGE_MAP.get(raw_code, raw_code.title())
            confidence = round(float(top.prob), 4)

            logger.info(
                "Language detected via langdetect: %s (%s), confidence=%.4f",
                lang_name,
                raw_code,
                confidence,
            )
            return LanguageResult(
                code=raw_code,
                name=lang_name,
                confidence=confidence,
                source="langdetect",
            )
        except ImportError:
            logger.warning(
                "langdetect not installed. Install with: pip install langdetect"
            )
        except Exception as exc:
            logger.warning("langdetect failed: %s", exc)

        return None
