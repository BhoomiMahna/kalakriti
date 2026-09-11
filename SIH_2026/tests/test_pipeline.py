"""
tests/test_pipeline.py
~~~~~~~~~~~~~~~~~~~~~~~~

End-to-end integration test for the ArtisanProductPipeline.

All model calls (ASR, translation, LLM) are mocked so the test runs
without downloading any models or requiring any API keys.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from artisan_ai.asr.base import TranscriptResult
from artisan_ai.config import Config
from artisan_ai.extraction.product_schema import (
    EvidencedField,
    ProductFacts,
    ProductListing,
    ValidationResult,
)
from artisan_ai.language.detection import LanguageResult
from artisan_ai.pipeline import ArtisanProductPipeline
from artisan_ai.translation.base import TranslationResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

PUNJABI_TRANSCRIPT = TranscriptResult(
    transcript="ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ। ਇਹ ਅਸੀਂ ਹੱਥ ਨਾਲ ਬਣਾਇਆ ਹੈ।",
    language_code="pa",
    language_name="Punjabi",
    confidence=0.97,
    model_name="whisper-large-v3",
)

ENGLISH_TRANSLATION = TranslationResult(
    translated_text="This is a Phulkari dupatta. We made it by hand. It uses cotton fabric and has red and yellow embroidery.",
    source_language="pa",
    target_language="en",
    model_name="ai4bharat/indictrans2-indic-en-dist-200M",
)

PRODUCT_FACTS = ProductFacts(
    product_name=EvidencedField(value="Phulkari Dupatta", status="supported", evidence="This is a Phulkari dupatta"),
    category=EvidencedField(value="Clothing", status="supported", evidence="dupatta"),
    subcategory=EvidencedField(value="Dupatta", status="supported", evidence="dupatta"),
    material=EvidencedField(value=["Cotton"], status="supported", evidence="cotton fabric"),
    colors=EvidencedField(value=["Red", "Yellow"], status="supported", evidence="red and yellow embroidery"),
    craft_type=EvidencedField(value="Handmade", status="supported", evidence="made it by hand"),
    craft_technique=EvidencedField(value="Phulkari embroidery", status="supported", evidence="Phulkari dupatta"),
    production_method=EvidencedField(value="Handmade", status="supported", evidence="made it by hand"),
)

PRODUCT_LISTING = ProductListing(
    title="Handcrafted Phulkari Cotton Dupatta",
    short_description="A hand-embroidered Phulkari dupatta crafted from cotton with red and yellow threadwork.",
    description="This dupatta is handcrafted using the Phulkari embroidery technique. Made from cotton fabric, it features detailed red and yellow embroidery applied entirely by hand.",
    highlights=["Handmade Phulkari embroidery", "Cotton fabric", "Red and yellow colour combination"],
    keywords=["phulkari", "dupatta", "handmade", "cotton"],
)

VALIDATION_RESULT = ValidationResult(valid=True, unsupported_claims=[], notes="")


# ── Mock setup ────────────────────────────────────────────────────────────────

def _make_pipeline() -> ArtisanProductPipeline:
    """Create a pipeline with all components mocked."""
    config = Config()
    config.google_api_key = "test-key"

    # Mock ASR
    mock_asr = MagicMock()
    mock_asr.transcribe.return_value = PUNJABI_TRANSCRIPT

    # Mock translator
    mock_translator = MagicMock()
    mock_translator.translate.return_value = ENGLISH_TRANSLATION

    # Mock preprocessor
    from artisan_ai.audio.preprocessing import PreprocessedAudio
    mock_preprocessor = MagicMock()
    mock_preprocessor.process.return_value = PreprocessedAudio(
        path="/tmp/processed.wav",
        sample_rate=16000,
        channels=1,
        duration_seconds=5.0,
        original_path="/tmp/original.wav",
    )

    pipeline = ArtisanProductPipeline(
        config=config,
        asr_provider=mock_asr,
        translation_provider=mock_translator,
        preprocessor=mock_preprocessor,
    )

    # Mock extractor, generator, validator
    pipeline.extractor = MagicMock()
    pipeline.extractor.extract.return_value = PRODUCT_FACTS

    pipeline.description_generator = MagicMock()
    pipeline.description_generator.generate.return_value = PRODUCT_LISTING

    pipeline.validator = MagicMock()
    pipeline.validator.validate.return_value = VALIDATION_RESULT

    # Mock follow-up generator (language detection still runs real)
    pipeline.followup_generator.generate_questions = MagicMock(return_value=[])

    return pipeline


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestPipelineProcess:
    def test_returns_required_keys(self):
        pipeline = _make_pipeline()
        result = pipeline.process("fake_audio.wav")

        required_keys = [
            "language", "transcription", "translation",
            "product_facts", "product_facts_with_evidence",
            "missing_fields", "follow_up_questions", "listing", "validation"
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_language_detection(self):
        pipeline = _make_pipeline()
        result = pipeline.process("fake_audio.wav")

        assert result["language"]["code"] == "pa"
        assert result["language"]["name"] == "Punjabi"

    def test_original_transcript_preserved(self):
        pipeline = _make_pipeline()
        result = pipeline.process("fake_audio.wav")

        assert result["transcription"]["original"] == PUNJABI_TRANSCRIPT.transcript

    def test_english_translation_present(self):
        pipeline = _make_pipeline()
        result = pipeline.process("fake_audio.wav")

        assert "Phulkari" in result["translation"]["english"]

    def test_product_facts_structure(self):
        pipeline = _make_pipeline()
        result = pipeline.process("fake_audio.wav")

        facts = result["product_facts"]
        assert facts["product_name"] == "Phulkari Dupatta"
        assert facts["material"] == ["Cotton"]
        assert facts["colors"] == ["Red", "Yellow"]
        assert facts["region"] is None  # Not hallucinated

    def test_no_hallucinated_region(self):
        """Region must be null even for Phulkari (Punjabi craft)."""
        pipeline = _make_pipeline()
        result = pipeline.process("fake_audio.wav")

        assert result["product_facts"]["region"] is None

    def test_listing_structure(self):
        pipeline = _make_pipeline()
        result = pipeline.process("fake_audio.wav")

        listing = result["listing"]
        assert "title" in listing
        assert "description" in listing
        assert "highlights" in listing
        assert "keywords" in listing
        assert isinstance(listing["highlights"], list)

    def test_validation_result(self):
        pipeline = _make_pipeline()
        result = pipeline.process("fake_audio.wav")

        validation = result["validation"]
        assert validation["valid"] is True
        assert validation["unsupported_claims"] == []

    def test_evidence_dict_present(self):
        """product_facts_with_evidence should contain evidence strings."""
        pipeline = _make_pipeline()
        result = pipeline.process("fake_audio.wav")

        evidence = result["product_facts_with_evidence"]
        assert "product_name" in evidence
        assert evidence["product_name"]["evidence"] != ""

    def test_english_audio_skips_translation(self):
        """Pipeline should not call translator for English audio."""
        pipeline = _make_pipeline()
        pipeline.asr.transcribe.return_value = TranscriptResult(
            transcript="This is a handmade shawl.",
            language_code="en",
            language_name="English",
            confidence=0.99,
            model_name="whisper-large-v3",
        )

        result = pipeline.process("english_audio.wav")

        pipeline.translator.translate.assert_not_called()
        assert result["translation"]["model"] == "passthrough"


class TestPipelineFactMerge:
    def test_merge_preserves_supported_fields(self):
        existing = {
            "product_name": {"value": "Phulkari Dupatta", "status": "supported", "evidence": ""},
            "material": None,
        }
        new = {
            "product_name": {"value": "Different Name", "status": "uncertain", "evidence": ""},
            "material": {"value": ["Silk"], "status": "supported", "evidence": "silk mentioned"},
        }
        merged = ArtisanProductPipeline._merge_facts(existing, new)

        # product_name should be preserved (existing was "supported")
        assert merged["product_name"]["value"] == "Phulkari Dupatta"
        # material should be filled in (was None)
        assert merged["material"]["value"] == ["Silk"]

    def test_merge_fills_missing_fields(self):
        existing = {"color": None, "material": None}
        new = {"color": "Red", "material": "Cotton"}
        merged = ArtisanProductPipeline._merge_facts(existing, new)
        assert merged["color"] == "Red"
        assert merged["material"] == "Cotton"
