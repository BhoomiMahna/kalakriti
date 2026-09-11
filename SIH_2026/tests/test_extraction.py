"""
tests/test_extraction.py
~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for product fact extraction.

These tests mock the LLM call so no API key is required.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from artisan_ai.config import Config
from artisan_ai.extraction.extractor import ProductExtractor, _user_prompt
from artisan_ai.extraction.product_schema import (
    EvidencedField,
    ProductFacts,
    ProductListing,
    ValidationResult,
    FollowUpQuestion,
)


# ── ProductFacts schema tests ──────────────────────────────────────────────────

class TestProductFacts:
    def test_all_null(self):
        facts = ProductFacts()
        assert facts.product_name is None
        assert facts.material is None
        assert facts.colors is None

    def test_evidenced_field(self):
        field = EvidencedField(
            value="Cotton",
            status="supported",
            evidence="It is made using cotton cloth.",
        )
        assert field.value == "Cotton"
        assert field.status == "supported"

    def test_list_value_in_evidenced_field(self):
        field = EvidencedField(
            value=["Red", "Yellow"],
            status="supported",
            evidence="red and yellow embroidery",
        )
        assert isinstance(field.value, list)
        assert "Red" in field.value

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            EvidencedField(value="Cotton", status="invented")  # type: ignore[arg-type]

    def test_get_category_str(self):
        facts = ProductFacts(
            category=EvidencedField(value="Clothing", status="supported", evidence="dupatta")
        )
        assert facts.get_category_str() == "Clothing"

    def test_get_category_str_none(self):
        facts = ProductFacts()
        assert facts.get_category_str() == ""

    def test_to_flat_dict(self):
        facts = ProductFacts(
            product_name=EvidencedField(value="Phulkari Dupatta", status="supported", evidence=""),
            material=EvidencedField(value=["Cotton"], status="supported", evidence="cotton cloth"),
            colors=EvidencedField(value=["Red", "Yellow"], status="supported", evidence="red and yellow"),
        )
        flat = facts.to_flat_dict()
        assert flat["product_name"] == "Phulkari Dupatta"
        assert flat["material"] == ["Cotton"]
        assert flat["colors"] == ["Red", "Yellow"]
        assert flat["dimensions"] is None

    def test_to_evidence_dict(self):
        facts = ProductFacts(
            product_name=EvidencedField(value="Phulkari Dupatta", status="supported", evidence="this is a phulkari dupatta"),
        )
        evidence = facts.to_evidence_dict()
        assert evidence["product_name"]["value"] == "Phulkari Dupatta"
        assert evidence["product_name"]["evidence"] == "this is a phulkari dupatta"


# ── ProductExtractor tests ─────────────────────────────────────────────────────

SAMPLE_LLM_RESPONSE = {
    "product_name": {"value": "Phulkari Dupatta", "status": "supported", "evidence": "This is a Phulkari dupatta"},
    "category": {"value": "Clothing", "status": "supported", "evidence": "dupatta"},
    "subcategory": {"value": "Dupatta", "status": "supported", "evidence": "dupatta"},
    "material": {"value": ["Cotton"], "status": "supported", "evidence": "cotton fabric"},
    "colors": {"value": ["Red", "Yellow"], "status": "supported", "evidence": "red and yellow embroidery"},
    "dimensions": None,
    "weight": None,
    "craft_type": {"value": "Handmade", "status": "supported", "evidence": "made it by hand"},
    "craft_technique": {"value": "Phulkari embroidery", "status": "supported", "evidence": "Phulkari dupatta"},
    "production_method": {"value": "Handmade", "status": "supported", "evidence": "made it by hand"},
    "region": None,
    "production_time": None,
    "usage": None,
    "cultural_significance": None,
    "care_instructions": None,
}


class TestProductExtractor:
    def _make_config(self):
        config = Config()
        config.google_api_key = "test-key"
        return config

    def test_extract_valid_response(self):
        config = self._make_config()
        extractor = ProductExtractor(config=config)

        with patch("artisan_ai.extraction.extractor._call_llm") as mock_llm:
            mock_llm.return_value = json.dumps(SAMPLE_LLM_RESPONSE)
            facts = extractor.extract(
                "This is a Phulkari dupatta. We made it by hand. "
                "It uses cotton fabric and has red and yellow embroidery."
            )

        assert facts.product_name.value == "Phulkari Dupatta"
        assert facts.material.value == ["Cotton"]
        assert facts.colors.value == ["Red", "Yellow"]
        assert facts.region is None
        assert facts.dimensions is None

    def test_no_hallucinated_region(self):
        """Region must be null even for Phulkari dupatta (a well-known Punjabi craft)."""
        config = self._make_config()
        extractor = ProductExtractor(config=config)

        with patch("artisan_ai.extraction.extractor._call_llm") as mock_llm:
            mock_llm.return_value = json.dumps(SAMPLE_LLM_RESPONSE)
            facts = extractor.extract(
                "This is a Phulkari dupatta. We made it by hand."
            )

        # Region must NOT be inferred from craft type
        assert facts.region is None

    def test_retry_on_invalid_json(self):
        config = self._make_config()
        extractor = ProductExtractor(config=config)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return "NOT VALID JSON {{{"
            return json.dumps(SAMPLE_LLM_RESPONSE)

        with patch("artisan_ai.extraction.extractor._call_llm", side_effect=side_effect):
            facts = extractor.extract("Some product description.")

        assert call_count == 2
        assert facts.product_name is not None

    def test_raises_after_max_retries(self):
        config = self._make_config()
        config.llm_max_retries = 2
        extractor = ProductExtractor(config=config)

        with patch("artisan_ai.extraction.extractor._call_llm", return_value="INVALID JSON"):
            with pytest.raises(RuntimeError, match="failed after"):
                extractor.extract("Some product description.")

    def test_markdown_fences_stripped(self):
        config = self._make_config()
        extractor = ProductExtractor(config=config)

        wrapped = f"```json\n{json.dumps(SAMPLE_LLM_RESPONSE)}\n```"

        with patch("artisan_ai.extraction.extractor._call_llm", return_value=wrapped):
            facts = extractor.extract("Test.")

        assert facts.product_name is not None


# ── Output schemas ────────────────────────────────────────────────────────────

class TestProductListing:
    def test_basic_creation(self):
        listing = ProductListing(
            title="Test Product",
            short_description="A test product.",
            description="This is a test product description.",
            highlights=["Feature 1", "Feature 2"],
            keywords=["test", "product"],
        )
        assert listing.title == "Test Product"
        assert len(listing.highlights) == 2

    def test_empty_highlights_allowed(self):
        listing = ProductListing(
            title="Test",
            short_description="Short.",
            description="Desc.",
        )
        assert listing.highlights == []
        assert listing.keywords == []


class TestFollowUpQuestion:
    def test_creation(self):
        q = FollowUpQuestion(
            field="dimensions",
            question_en="What are the approximate dimensions?",
            question_local="ਇਸ ਦਾ ਆਕਾਰ ਕੀ ਹੈ?",
        )
        assert q.field == "dimensions"
        assert q.question_local == "ਇਸ ਦਾ ਆਕਾਰ ਕੀ ਹੈ?"

    def test_local_defaults_empty(self):
        q = FollowUpQuestion(field="weight", question_en="What is the weight?")
        assert q.question_local == ""


class TestValidationResult:
    def test_valid(self):
        result = ValidationResult(valid=True, unsupported_claims=[])
        assert result.valid is True
        assert result.unsupported_claims == []

    def test_invalid_with_claims(self):
        result = ValidationResult(
            valid=False,
            unsupported_claims=["Eco-friendly material"],
        )
        assert not result.valid
        assert len(result.unsupported_claims) == 1
