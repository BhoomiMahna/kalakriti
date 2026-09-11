"""
artisan_ai.pipeline
~~~~~~~~~~~~~~~~~~~~~

Main orchestrator for the Artisan Product AI pipeline.

Usage::

    from artisan_ai import ArtisanProductPipeline

    pipeline = ArtisanProductPipeline()
    result = pipeline.process("artisan_audio.wav")

The ``result`` dictionary matches the final output JSON specification.

Architecture
------------
::

    AUDIO INPUT
         ↓
    AudioPreprocessor     (audio/preprocessing.py)
         ↓
    ASRProvider           (asr/whisper_asr.py)
         ↓
    ORIGINAL LANGUAGE TRANSCRIPT
         ↓
    LanguageDetector      (language/detection.py)
         ↓
    TranslationProvider   (translation/indictrans.py)
         ↓
    ENGLISH TRANSLATION
         ↓
    ProductExtractor      (extraction/extractor.py)
         ↓
    STRUCTURED PRODUCT JSON
         ↓
    FollowUpGenerator     (followup/question_generator.py)
         ↓
    MISSING INFORMATION + QUESTIONS
         ↓
    DescriptionGenerator  (generation/description_generator.py)
         ↓
    FactualValidator      (validation/factual_validator.py)
         ↓
    FINAL OUTPUT JSON
"""

from __future__ import annotations

import logging
from typing import Any

from artisan_ai.audio.preprocessing import AudioPreprocessor
from artisan_ai.asr.base import ASRProvider
from artisan_ai.asr.whisper_asr import WhisperASR
from artisan_ai.config import Config
from artisan_ai.extraction.extractor import ProductExtractor
from artisan_ai.extraction.product_schema import ProductFacts
from artisan_ai.followup.question_generator import FollowUpGenerator
from artisan_ai.generation.description_generator import DescriptionGenerator
from artisan_ai.language.detection import LanguageDetector
from artisan_ai.translation.base import TranslationProvider
from artisan_ai.translation.indictrans import IndicTransProvider
from artisan_ai.translation.opus_mt import OpusMTProvider
from artisan_ai.validation.factual_validator import FactualValidator

logger = logging.getLogger(__name__)


class ArtisanProductPipeline:
    """End-to-end pipeline: artisan audio → professional product listing.

    Parameters
    ----------
    config:
        Optional :class:`~artisan_ai.config.Config` instance.
        If omitted, values are loaded from environment variables / ``.env``.
    asr_provider:
        Custom ASR backend.  Defaults to :class:`WhisperASR`.
    translation_provider:
        Custom translation backend.  Defaults to ``IndicTransProvider`` or
        ``OpusMTProvider`` based on config.
    preprocessor:
        Custom :class:`AudioPreprocessor`.  Defaults to the standard pipeline.

    Examples
    --------
    **Basic usage** ::

        pipeline = ArtisanProductPipeline()
        result = pipeline.process("artisan_audio.wav")

    **Custom providers** ::

        from artisan_ai.asr.indic_asr import IndicConformerASR
        pipeline = ArtisanProductPipeline(
            asr_provider=IndicConformerASR(model_path="...", language="hi")
        )

    **Follow-up update** ::

        updated = pipeline.update_product_facts(
            existing_facts=result["product_facts"],
            follow_up_audio="followup.wav",
        )
    """

    def __init__(
        self,
        config: Config | None = None,
        asr_provider: ASRProvider | None = None,
        translation_provider: TranslationProvider | None = None,
        preprocessor: AudioPreprocessor | None = None,
    ) -> None:
        self.config = config or Config()
        device = self.config.resolve_device()

        # ── Components ────────────────────────────────────────────────────────
        self.preprocessor = preprocessor or AudioPreprocessor()

        if asr_provider is not None:
            self.asr = asr_provider
        elif self.config.asr_provider == "bhashini":
            from artisan_ai.asr.bhashini_asr import BhashiniASR
            self.asr = BhashiniASR(config=self.config)
        elif self.config.asr_provider == "sarvam":
            from artisan_ai.asr.sarvam_asr import SarvamASR
            self.asr = SarvamASR(config=self.config)
        else:
            self.asr = WhisperASR(
                model_size=self.config.whisper_model_size,
                device=device,
            )

        self.language_detector = LanguageDetector()

        if translation_provider is not None:
            self.translator = translation_provider
        elif self.config.translation_provider == "indictrans2":
            self.translator = IndicTransProvider(
                model_name=self.config.indictrans2_model,
                device=device,
            )
        else:
            self.translator = OpusMTProvider(device=device)

        self.extractor = ProductExtractor(config=self.config)
        self.followup_generator = FollowUpGenerator(config=self.config)
        self.description_generator = DescriptionGenerator(config=self.config)
        self.validator = FactualValidator(config=self.config)

    # ── Main entry point ──────────────────────────────────────────────────────

    def process(self, audio_path: str) -> dict[str, Any]:
        """Process an artisan audio file through the full pipeline.

        Parameters
        ----------
        audio_path:
            Path to the input audio file (.wav, .mp3, .m4a, .webm).

        Returns
        -------
        dict
            Complete structured output with transcript, translation,
            product facts, follow-up questions, listing, and validation.
        """
        logger.info("=" * 60)
        logger.info("ArtisanProductPipeline.process: %s", audio_path)

        # ── Stage 1: Audio preprocessing ─────────────────────────────────────
        logger.info("[1/7] Audio preprocessing ...")
        audio = self.preprocessor.process(audio_path)

        # ── Stage 2: Speech-to-text ───────────────────────────────────────────
        logger.info("[2/7] Speech-to-text ...")
        transcript_result = self.asr.transcribe(audio.path)
        logger.info(
            "Transcript (%s): %s",
            transcript_result.language_code,
            transcript_result.transcript[:80],
        )

        # ── Stage 3: Language detection ───────────────────────────────────────
        logger.info("[3/7] Language detection ...")
        language = self.language_detector.detect(
            asr_language_code=transcript_result.language_code,
            asr_confidence=transcript_result.confidence,
            transcript_text=transcript_result.transcript,
        )
        logger.info("Language: %s (%s)", language.name, language.code)

        # ── Stage 4: Translation ──────────────────────────────────────────────
        logger.info("[4/7] Translation to English ...")
        if language.code == "en":
            # Already English — no translation needed
            english_text = transcript_result.transcript
            translation_model = "passthrough"
        else:
            translation_result = self.translator.translate(
                text=transcript_result.transcript,
                source_language=language.code,
                target_language="en",
            )
            english_text = translation_result.translated_text
            translation_model = translation_result.model_name
        logger.info("Translation: %s ...", english_text[:80])

        # ── Stage 5: Product fact extraction ─────────────────────────────────
        logger.info("[5/7] Product fact extraction ...")
        facts = self.extractor.extract(english_text)

        # ── Stage 6: Missing fields + follow-up questions ─────────────────────
        logger.info("[6/7] Follow-up question generation ...")
        missing_fields = self.followup_generator.identify_missing_fields(facts)
        follow_up_questions = self.followup_generator.generate_questions(
            facts,
            language_code=language.code,
            language_name=language.name,
        )

        # ── Stage 7: Description generation + validation ─────────────────────
        logger.info("[7/7] Description generation and validation ...")
        listing, validation = self._generate_with_validation(facts)

        # ── Assemble final output ─────────────────────────────────────────────
        output = self._build_output(
            language=language,
            transcript_result=transcript_result,
            english_text=english_text,
            translation_model=translation_model,
            facts=facts,
            missing_fields=missing_fields,
            follow_up_questions=follow_up_questions,
            listing=listing,
            validation=validation,
        )

        logger.info("Pipeline complete.")
        logger.info("=" * 60)
        return output

    # ── Follow-up update ──────────────────────────────────────────────────────

    def update_product_facts(
        self,
        existing_facts: dict[str, Any],
        follow_up_audio: str,
    ) -> dict[str, Any]:
        """Merge follow-up artisan audio into existing product facts.

        Parameters
        ----------
        existing_facts:
            The ``product_facts`` dict from a previous :meth:`process` call.
        follow_up_audio:
            Path to the new artisan audio recording (follow-up answer).

        Returns
        -------
        dict
            Updated pipeline output with merged facts.

        Notes
        -----
        Existing ``supported`` fields are NEVER overwritten by uncertain or
        missing new values.  Only ``None`` or ``missing`` fields are updated.
        """
        logger.info("update_product_facts: processing follow-up audio ...")

        # Process the follow-up audio to get new facts
        follow_up_result = self.process(follow_up_audio)
        new_facts_dict = follow_up_result["product_facts"]

        # Merge: prefer existing supported values
        merged = self._merge_facts(existing_facts, new_facts_dict)

        # Rebuild output using merged facts
        facts_obj = ProductFacts(**{
            k: v for k, v in merged.items()
            if k in ProductFacts.model_fields
        })

        missing_fields = self.followup_generator.identify_missing_fields(facts_obj)
        follow_up_questions = self.followup_generator.generate_questions(
            facts_obj,
            language_code=follow_up_result["language"]["code"],
            language_name=follow_up_result["language"]["name"],
        )
        listing, validation = self._generate_with_validation(facts_obj)

        follow_up_result["product_facts"] = merged
        follow_up_result["missing_fields"] = missing_fields
        follow_up_result["follow_up_questions"] = [
            q.model_dump() for q in follow_up_questions
        ]
        follow_up_result["listing"] = listing.model_dump()
        follow_up_result["validation"] = validation.model_dump()

        return follow_up_result

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _generate_with_validation(self, facts: ProductFacts):
        """Generate listing and run factual validation, with auto-retry."""
        from artisan_ai.extraction.product_schema import ProductListing, ValidationResult

        listing = self.description_generator.generate(facts)
        validation = self.validator.validate(facts, listing)

        # If unsupported claims found, regenerate once
        if not validation.valid:
            logger.warning(
                "Validation failed (%d unsupported claims). Regenerating ...",
                len(validation.unsupported_claims),
            )
            listing = self.description_generator.generate(facts)
            validation = self.validator.validate(facts, listing)

            if not validation.valid:
                logger.warning(
                    "Regeneration still has %d unsupported claims. "
                    "Returning with warnings.",
                    len(validation.unsupported_claims),
                )

        return listing, validation

    @staticmethod
    def _merge_facts(
        existing: dict[str, Any],
        new: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge new facts into existing, preserving supported values."""
        merged = dict(existing)
        for key, new_value in new.items():
            if new_value is None:
                continue  # New value is null — keep existing

            existing_value = existing.get(key)
            if existing_value is None:
                merged[key] = new_value  # Fill previously missing field
                continue

            # If existing is an EvidencedField-like dict, only override if
            # the existing status is not "supported"
            if isinstance(existing_value, dict) and "status" in existing_value:
                if existing_value["status"] == "supported":
                    continue  # Keep the reliable existing value
            merged[key] = new_value

        return merged

    @staticmethod
    def _build_output(
        *,
        language,
        transcript_result,
        english_text: str,
        translation_model: str,
        facts: ProductFacts,
        missing_fields: list[str],
        follow_up_questions,
        listing,
        validation,
    ) -> dict[str, Any]:
        """Assemble the final output dictionary."""
        return {
            "language": {
                "code": language.code,
                "name": language.name,
                "confidence": language.confidence,
                "detection_source": language.source,
            },
            "transcription": {
                "original": transcript_result.transcript,
                "asr_model": transcript_result.model_name,
            },
            "translation": {
                "english": english_text,
                "model": translation_model,
            },
            "product_facts": facts.to_flat_dict(),
            "product_facts_with_evidence": facts.to_evidence_dict(),
            "missing_fields": missing_fields,
            "follow_up_questions": [q.model_dump() for q in follow_up_questions],
            "listing": listing.model_dump(),
            "validation": validation.model_dump(),
        }
