"""
artisan_ai.extraction.extractor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Structured product fact extractor.

Uses an LLM in JSON mode (Gemini primary, OpenAI fallback) to extract
product attributes from the artisan's English translation.

Critical design constraints
----------------------------
* The LLM receives ONLY the artisan's translated statement.
* The system prompt explicitly forbids inference of unsupported attributes.
* If something was not stated, the field must be ``null``.
* Output is validated against the Pydantic ``ProductFacts`` schema.
* Up to ``Config.llm_max_retries`` retries on schema validation failure.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from artisan_ai.config import Config
from artisan_ai.extraction.product_schema import EvidencedField, ProductFacts

logger = logging.getLogger(__name__)

# ── Extraction system prompt ──────────────────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are a product information extractor for an e-commerce platform that sells Indian artisan products.

Your task: extract structured product facts from an artisan's spoken statement (provided as an English translation).

CRITICAL RULES — read carefully:
1. Extract ONLY information explicitly stated by the artisan.
2. NEVER infer or assume any attribute not directly mentioned.
3. If a field was not mentioned, set it to null — do not guess.
4. Do NOT infer material from product type (e.g., do not assume "cotton" because it's a dupatta).
5. Do NOT infer region from craft type (e.g., do not assume "Punjab" because the craft is Phulkari).
6. Do NOT infer certifications, sustainability, or historical significance unless explicitly stated.
7. For list fields (material, colors), return an array; for others, a string.

For each field you extract, include:
- "value": the extracted value
- "status": "supported" (clearly stated), "uncertain" (implied but not explicit), or "missing" (not mentioned)
- "evidence": the exact phrase from the artisan's statement that supports this value

Return a JSON object matching this exact schema:
{
  "product_name": {"value": string|null, "status": "supported"|"uncertain"|"missing", "evidence": string} | null,
  "category": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "subcategory": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "material": {"value": [string]|null, "status": "...", "evidence": "..."} | null,
  "colors": {"value": [string]|null, "status": "...", "evidence": "..."} | null,
  "dimensions": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "weight": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "craft_type": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "craft_technique": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "production_method": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "region": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "production_time": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "usage": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "cultural_significance": {"value": string|null, "status": "...", "evidence": "..."} | null,
  "care_instructions": {"value": string|null, "status": "...", "evidence": "..."} | null
}

Set any field to null (not an object) if the artisan did not mention it at all.
Do NOT add any text outside the JSON object."""


def _user_prompt(english_translation: str) -> str:
    return (
        f"Extract product facts from this artisan's statement:\n\n"
        f"{english_translation}\n\n"
        f"Return ONLY a valid JSON object."
    )


# ── LLM client helpers ────────────────────────────────────────────────────────

def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    config: Config,
) -> str:
    import google.generativeai as genai  # type: ignore[import]

    genai.configure(api_key=config.google_api_key)
    model = genai.GenerativeModel(
        model_name=config.gemini_model,
        system_instruction=system_prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.0,  # Deterministic for extraction
        ),
    )
    response = model.generate_content(user_prompt)
    return response.text


def _call_openai(
    system_prompt: str,
    user_prompt: str,
    config: Config,
) -> str:
    from openai import OpenAI  # type: ignore[import]

    client = OpenAI(api_key=config.openai_api_key)
    response = client.chat.completions.create(
        model=config.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    return response.choices[0].message.content or ""


def _call_llm(system_prompt: str, user_prompt: str, config: Config) -> str:
    provider = config.get_llm_provider()
    if provider == "gemini":
        return _call_gemini(system_prompt, user_prompt, config)
    return _call_openai(system_prompt, user_prompt, config)


# ── Main extractor ────────────────────────────────────────────────────────────

class ProductExtractor:
    """Extract structured product facts from an English translation.

    Parameters
    ----------
    config:
        Pipeline configuration.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def extract(self, english_translation: str) -> ProductFacts:
        """Extract product facts from *english_translation*.

        Parameters
        ----------
        english_translation:
            The artisan's statement translated to English.

        Returns
        -------
        ProductFacts
            Validated, evidence-annotated product facts.

        Raises
        ------
        RuntimeError
            If the LLM fails to produce valid JSON after all retries.
        """
        system_prompt = EXTRACTION_SYSTEM_PROMPT
        user_prompt = _user_prompt(english_translation)
        last_error: Exception | None = None

        for attempt in range(1, self.config.llm_max_retries + 1):
            try:
                logger.info(
                    "Extraction attempt %d/%d ...", attempt, self.config.llm_max_retries
                )
                raw = _call_llm(system_prompt, user_prompt, self.config)
                facts = self._parse_and_validate(raw)
                logger.info("Extraction successful.")
                return facts
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    "Attempt %d failed: %s. Retrying ...", attempt, exc
                )
                last_error = exc
                # Add the error to the user prompt so the LLM can self-correct
                user_prompt = (
                    f"{_user_prompt(english_translation)}\n\n"
                    f"[Previous attempt produced invalid JSON: {exc}. "
                    f"Return only valid JSON.]"
                )

        raise RuntimeError(
            f"ProductExtractor failed after {self.config.llm_max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def _parse_and_validate(self, raw: str) -> ProductFacts:
        """Parse *raw* JSON string and validate against :class:`ProductFacts`."""
        # Strip accidental markdown code fences
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(
                line for line in lines if not line.startswith("```")
            )

        data: dict[str, Any] = json.loads(raw)
        return ProductFacts(**data)
