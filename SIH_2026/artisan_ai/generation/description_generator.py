"""
artisan_ai.generation.description_generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Professional English product listing generator.

Critical constraint
--------------------
The LLM receives the structured ``ProductFacts`` as its ONLY factual
source.  It does NOT receive the raw transcript or audio.

Generation rules (enforced in the system prompt):
  1. Use only information present in the product facts JSON.
  2. Never invent material, dimensions, weight, certifications, or origin.
  3. Never claim sustainability, eco-friendliness, or organic unless stated.
  4. Never invent cultural or historical significance.
  5. Do not use excessive marketing superlatives.
  6. Write professional e-commerce English.
"""

from __future__ import annotations

import json
import logging

from artisan_ai.config import Config
from artisan_ai.extraction.product_schema import ProductFacts, ProductListing

logger = logging.getLogger(__name__)


# ── System prompt ─────────────────────────────────────────────────────────────

GENERATION_SYSTEM_PROMPT = """You are a professional e-commerce copywriter specialising in Indian artisan products.

Your task: write a product listing for an online marketplace based ONLY on the structured product facts provided.

STRICT RULES:
1. Use ONLY the information present in the provided product facts JSON.
2. Never invent or infer any attribute not present in the facts.
3. Do NOT claim the product is "eco-friendly", "sustainable", "organic", "certified", "premium", "luxury", "authentic", "traditional", or "award-winning" unless the facts explicitly state it.
4. Do NOT invent cultural or historical significance.
5. Do NOT invent regional origin unless "region" is present in the facts.
6. Do NOT invent materials.
7. Do NOT invent dimensions or weight.
8. Write professional, clear e-commerce English. Avoid marketing fluff.
9. If a fact field is null, simply omit that information from the description.
10. Preserve any craft technique name exactly as provided (e.g., "Phulkari", "Kantha", "Warli").

Return a JSON object with this exact structure:
{
  "title": "Short product title (max 80 characters)",
  "short_description": "One-sentence summary (max 150 characters)",
  "description": "2-4 paragraph product description",
  "highlights": ["Bullet 1", "Bullet 2", ...],
  "keywords": ["keyword1", "keyword2", ...]
}

Return ONLY the JSON object, no other text."""


def _generation_user_prompt(facts: ProductFacts) -> str:
    flat = facts.to_flat_dict()
    facts_json = json.dumps(flat, ensure_ascii=False, indent=2)
    return (
        f"Generate a product listing based ONLY on these facts:\n\n"
        f"{facts_json}\n\n"
        f"If a field is null, do not mention it in the listing."
    )


# ── LLM call ──────────────────────────────────────────────────────────────────

def _call_gemini(system: str, user: str, config: Config) -> str:
    import google.generativeai as genai  # type: ignore[import]

    genai.configure(api_key=config.google_api_key)
    model = genai.GenerativeModel(
        model_name=config.gemini_model,
        system_instruction=system,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=config.generation_temperature,
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
        temperature=config.generation_temperature,
    )
    return response.choices[0].message.content or ""


def _call_llm(system: str, user: str, config: Config) -> str:
    provider = config.get_llm_provider()
    if provider == "gemini":
        return _call_gemini(system, user, config)
    return _call_openai(system, user, config)


# ── Main generator ────────────────────────────────────────────────────────────

class DescriptionGenerator:
    """Generate professional product listings from structured product facts.

    Parameters
    ----------
    config:
        Pipeline configuration.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def generate(self, facts: ProductFacts) -> ProductListing:
        """Generate a product listing from *facts*.

        Parameters
        ----------
        facts:
            Validated, structured product facts.

        Returns
        -------
        ProductListing
            Title, descriptions, highlights, and keywords.

        Raises
        ------
        RuntimeError
            If the LLM fails to produce valid output after all retries.
        """
        user_prompt = _generation_user_prompt(facts)
        last_error: Exception | None = None

        for attempt in range(1, self.config.llm_max_retries + 1):
            try:
                logger.info(
                    "Description generation attempt %d/%d ...",
                    attempt,
                    self.config.llm_max_retries,
                )
                raw = _call_llm(GENERATION_SYSTEM_PROMPT, user_prompt, self.config)
                listing = self._parse(raw)
                logger.info("Description generated successfully.")
                return listing
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Attempt %d failed: %s", attempt, exc)
                last_error = exc

        raise RuntimeError(
            f"DescriptionGenerator failed after {self.config.llm_max_retries} "
            f"attempts. Last error: {last_error}"
        )

    def _parse(self, raw: str) -> ProductListing:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = "\n".join(l for l in raw.splitlines() if not l.startswith("```"))
        data = json.loads(raw)
        return ProductListing(**data)
