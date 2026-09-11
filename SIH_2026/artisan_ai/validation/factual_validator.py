"""
artisan_ai.validation.factual_validator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Two-stage factual validation for generated product descriptions.

Stage 1 — Rule-based
    Scans the description for a list of forbidden phrases that represent
    unsupported marketing claims (e.g. "eco-friendly", "organic", "premium
    quality").  Any match is an instant unsupported claim.

Stage 2 — LLM-based
    Asks the LLM to compare the generated description against the structured
    product facts and identify any claim in the description that cannot be
    traced back to the facts.

If unsupported claims are found, the pipeline can:
  a) Remove the offending sentences, or
  b) Trigger description regeneration (up to ``Config.llm_max_retries``).
"""

from __future__ import annotations

import json
import logging
import re

from artisan_ai.config import Config
from artisan_ai.extraction.product_schema import (
    ProductFacts,
    ProductListing,
    ValidationResult,
)

logger = logging.getLogger(__name__)


# ── Stage 1: Rule-based forbidden phrases ────────────────────────────────────

DEFAULT_FORBIDDEN_PATTERNS: list[str] = [
    r"\beco[-\s]?friendly\b",
    r"\bsustainable\b",
    r"\borganic\b",
    r"\bcertified\b",
    r"\bpremium quality\b",
    r"\bluxury\b",
    r"\bworld[-\s]?class\b",
    r"\baward[-\s]?winning\b",
    r"\bbest[-\s]?in[-\s]?class\b",
    r"\bhandpicked\b",
    r"\bexclusive\b",
]


def _rule_based_check(
    listing: ProductListing,
    forbidden_phrases: list[str],
) -> list[str]:
    """Return list of forbidden phrases found in the listing text."""
    full_text = " ".join(
        [
            listing.title,
            listing.short_description,
            listing.description,
            " ".join(listing.highlights),
        ]
    ).lower()

    found: list[str] = []
    for pattern in forbidden_phrases:
        if re.search(pattern, full_text, re.IGNORECASE):
            found.append(pattern.replace(r"\b", "").replace("[-\\s]?", "-"))
    return found


# ── Stage 2: LLM-based claim verification ────────────────────────────────────

VALIDATION_SYSTEM_PROMPT = """You are a factual accuracy auditor for an e-commerce platform selling Indian artisan products.

Your task: compare a generated product description against the structured product facts that were used to generate it.
Identify any specific claim in the description that CANNOT be supported by the provided product facts.

Rules:
- A claim is "unsupported" if it states or implies a fact NOT present in the product facts JSON.
- Paraphrasing known facts is acceptable.
- Generic descriptive language ("well-crafted", "carefully made") is acceptable unless it implies a specific attribute not in the facts.
- Claims about material, dimensions, weight, region, certifications, sustainability, cultural history are NOT acceptable unless in the facts.

Return a JSON object:
{
  "valid": true|false,
  "unsupported_claims": ["Exact sentence or phrase that is unsupported", ...],
  "notes": "Optional explanation"
}

If there are no unsupported claims, return {"valid": true, "unsupported_claims": [], "notes": ""}.
Return ONLY the JSON object."""


def _validation_user_prompt(facts: ProductFacts, listing: ProductListing) -> str:
    facts_json = json.dumps(facts.to_flat_dict(), ensure_ascii=False, indent=2)
    listing_json = json.dumps(listing.model_dump(), ensure_ascii=False, indent=2)
    return (
        f"Product Facts:\n{facts_json}\n\n"
        f"Generated Listing:\n{listing_json}\n\n"
        f"Identify unsupported claims."
    )


def _call_gemini(system: str, user: str, config: Config) -> str:
    import google.generativeai as genai  # type: ignore[import]

    genai.configure(api_key=config.google_api_key)
    model = genai.GenerativeModel(
        model_name=config.gemini_model,
        system_instruction=system,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )
    return model.generate_content(user).text


def _call_openai(system: str, user: str, config: Config) -> str:
    from openai import OpenAI  # type: ignore[import]

    client = OpenAI(api_key=config.openai_api_key)
    response = client.chat.completions.create(
        model=config.openai_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    return response.choices[0].message.content or ""


def _call_llm(system: str, user: str, config: Config) -> str:
    provider = config.get_llm_provider()
    if provider == "gemini":
        return _call_gemini(system, user, config)
    return _call_openai(system, user, config)


# ── Main validator ────────────────────────────────────────────────────────────

class FactualValidator:
    """Validate that a generated listing contains no unsupported claims.

    Parameters
    ----------
    config:
        Pipeline configuration.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def validate(
        self,
        facts: ProductFacts,
        listing: ProductListing,
    ) -> ValidationResult:
        """Run both validation stages.

        Parameters
        ----------
        facts:
            The structured product facts.
        listing:
            The generated product listing.

        Returns
        -------
        ValidationResult
        """
        unsupported: list[str] = []

        # ── Stage 1: Rule-based ───────────────────────────────────────────────
        forbidden_found = _rule_based_check(
            listing, self.config.forbidden_unsupported_phrases
        )
        if forbidden_found:
            logger.warning(
                "Rule-based check found forbidden phrases: %s", forbidden_found
            )
            unsupported.extend(
                f"Forbidden phrase: '{p}'" for p in forbidden_found
            )

        # ── Stage 2: LLM-based ────────────────────────────────────────────────
        llm_result = self._llm_validate(facts, listing)
        if not llm_result.valid:
            logger.warning(
                "LLM validation found %d unsupported claim(s).",
                len(llm_result.unsupported_claims),
            )
            unsupported.extend(llm_result.unsupported_claims)

        # Deduplicate
        seen: set[str] = set()
        unique_unsupported: list[str] = []
        for item in unsupported:
            if item not in seen:
                seen.add(item)
                unique_unsupported.append(item)

        valid = len(unique_unsupported) == 0
        logger.info(
            "Validation result: valid=%s, unsupported_claims=%d",
            valid,
            len(unique_unsupported),
        )
        return ValidationResult(
            valid=valid,
            unsupported_claims=unique_unsupported,
            notes=llm_result.notes,
        )

    def _llm_validate(
        self,
        facts: ProductFacts,
        listing: ProductListing,
    ) -> ValidationResult:
        try:
            raw = _call_llm(
                VALIDATION_SYSTEM_PROMPT,
                _validation_user_prompt(facts, listing),
                self.config,
            )
            raw = raw.strip()
            if raw.startswith("```"):
                raw = "\n".join(l for l in raw.splitlines() if not l.startswith("```"))
            data = json.loads(raw)
            return ValidationResult(**data)
        except Exception as exc:
            logger.error("LLM validation failed: %s. Skipping LLM stage.", exc)
            return ValidationResult(valid=True, unsupported_claims=[], notes="LLM validation unavailable.")
