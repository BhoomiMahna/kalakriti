"""
tests/test_validation.py
~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for the FactualValidator.
"""

import json
from unittest.mock import patch

import pytest

from artisan_ai.config import Config
from artisan_ai.extraction.product_schema import (
    EvidencedField,
    ProductFacts,
    ProductListing,
    ValidationResult,
)
from artisan_ai.validation.factual_validator import (
    FactualValidator,
    _rule_based_check,
    DEFAULT_FORBIDDEN_PATTERNS,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_facts(**kwargs) -> ProductFacts:
    return ProductFacts(**kwargs)


def _make_listing(**kwargs) -> ProductListing:
    defaults = {
        "title": "Handcrafted Phulkari Cotton Dupatta",
        "short_description": "A hand-embroidered dupatta made from cotton.",
        "description": "This dupatta is made by hand using cotton fabric with red and yellow Phulkari embroidery.",
        "highlights": ["Handmade Phulkari embroidery", "Cotton fabric"],
        "keywords": ["phulkari", "dupatta", "cotton"],
    }
    defaults.update(kwargs)
    return ProductListing(**defaults)


def _make_config() -> Config:
    config = Config()
    config.google_api_key = "test-key"
    return config


# ── Rule-based tests ──────────────────────────────────────────────────────────

class TestRuleBasedCheck:
    def test_clean_description_passes(self):
        listing = _make_listing()
        found = _rule_based_check(listing, DEFAULT_FORBIDDEN_PATTERNS)
        assert found == []

    def test_eco_friendly_detected(self):
        listing = _make_listing(description="This is an eco-friendly dupatta.")
        found = _rule_based_check(listing, DEFAULT_FORBIDDEN_PATTERNS)
        assert any("eco" in f for f in found)

    def test_organic_detected(self):
        listing = _make_listing(description="Made from organic cotton.")
        found = _rule_based_check(listing, DEFAULT_FORBIDDEN_PATTERNS)
        assert any("organic" in f for f in found)

    def test_premium_quality_detected(self):
        listing = _make_listing(title="Premium Quality Dupatta")
        found = _rule_based_check(listing, DEFAULT_FORBIDDEN_PATTERNS)
        assert any("premium quality" in f for f in found)

    def test_case_insensitive(self):
        listing = _make_listing(description="This is an ECO-FRIENDLY product.")
        found = _rule_based_check(listing, DEFAULT_FORBIDDEN_PATTERNS)
        assert len(found) > 0

    def test_highlights_checked(self):
        listing = _make_listing(
            highlights=["Sustainable materials", "Handmade"]
        )
        found = _rule_based_check(listing, DEFAULT_FORBIDDEN_PATTERNS)
        assert any("sustainable" in f for f in found)


# ── LLM validation tests ──────────────────────────────────────────────────────

class TestFactualValidator:
    def _llm_valid_response(self):
        return json.dumps({
            "valid": True,
            "unsupported_claims": [],
            "notes": "",
        })

    def _llm_invalid_response(self, claims: list):
        return json.dumps({
            "valid": False,
            "unsupported_claims": claims,
            "notes": "Claims not in facts.",
        })

    def test_valid_listing_passes(self):
        config = _make_config()
        validator = FactualValidator(config=config)
        facts = _make_facts(
            product_name=EvidencedField(value="Phulkari Dupatta", status="supported", evidence=""),
            material=EvidencedField(value=["Cotton"], status="supported", evidence=""),
            craft_technique=EvidencedField(value="Phulkari embroidery", status="supported", evidence=""),
        )
        listing = _make_listing()

        with patch("artisan_ai.validation.factual_validator._call_llm", return_value=self._llm_valid_response()):
            result = validator.validate(facts, listing)

        assert result.valid is True
        assert result.unsupported_claims == []

    def test_forbidden_phrase_fails(self):
        config = _make_config()
        validator = FactualValidator(config=config)
        facts = _make_facts()
        listing = _make_listing(description="This is an eco-friendly and sustainable product.")

        with patch("artisan_ai.validation.factual_validator._call_llm", return_value=self._llm_valid_response()):
            result = validator.validate(facts, listing)

        assert result.valid is False
        assert any("eco" in c.lower() for c in result.unsupported_claims)

    def test_llm_unsupported_claim_detected(self):
        config = _make_config()
        validator = FactualValidator(config=config)
        facts = _make_facts()
        listing = _make_listing()

        hallucinated_claim = "Traditionally made in Punjab for generations."
        with patch(
            "artisan_ai.validation.factual_validator._call_llm",
            return_value=self._llm_invalid_response([hallucinated_claim]),
        ):
            result = validator.validate(facts, listing)

        assert result.valid is False
        assert hallucinated_claim in result.unsupported_claims

    def test_llm_failure_handled_gracefully(self):
        """If LLM fails, rule-based result should still be returned."""
        config = _make_config()
        validator = FactualValidator(config=config)
        facts = _make_facts()
        listing = _make_listing()  # No forbidden phrases

        with patch("artisan_ai.validation.factual_validator._call_llm", side_effect=Exception("Network error")):
            result = validator.validate(facts, listing)

        # Should still pass rule-based check (no forbidden phrases in default listing)
        assert result.valid is True

    def test_duplicate_claims_deduplicated(self):
        config = _make_config()
        validator = FactualValidator(config=config)
        facts = _make_facts()
        listing = _make_listing(description="This is an eco-friendly product.")

        # LLM also reports eco-friendly
        with patch(
            "artisan_ai.validation.factual_validator._call_llm",
            return_value=self._llm_invalid_response(["Eco-friendly claim"]),
        ):
            result = validator.validate(facts, listing)

        # Should not have exact duplicate entries
        assert len(result.unsupported_claims) == len(set(result.unsupported_claims))
