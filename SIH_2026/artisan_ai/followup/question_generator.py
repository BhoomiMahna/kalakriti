"""
artisan_ai.followup.question_generator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Follow-up question generator.

After extracting product facts, this module:
  1. Identifies missing fields that are important for the product's category.
  2. Generates English questions targeting each missing field.
  3. Translates questions into the artisan's detected language.

The parent application is responsible for:
  - Presenting the questions to the artisan.
  - Recording the artisan's audio response.
  - Passing the new audio back to ``pipeline.update_product_facts()``.
"""

from __future__ import annotations

import json
import logging

from artisan_ai.config import CATEGORY_REQUIRED_FIELDS, Config
from artisan_ai.extraction.product_schema import FollowUpQuestion, ProductFacts

logger = logging.getLogger(__name__)


# ── Question generation prompts ────────────────────────────────────────────────

def _questions_system_prompt() -> str:
    return """You are a helpful assistant generating follow-up questions for an artisan selling handmade products.

Your task: given a list of missing product fields, generate one clear, friendly, concise question in English for each field.
The questions should be in simple language appropriate for a rural artisan.

Return a JSON array:
[
  {"field": "field_name", "question_en": "What is the...?"},
  ...
]

Return ONLY the JSON array, no other text."""


def _questions_user_prompt(missing_fields: list[str], product_name: str) -> str:
    fields_list = "\n".join(f"- {f}" for f in missing_fields)
    return (
        f"Product: {product_name or 'handmade artisan product'}\n\n"
        f"Missing fields:\n{fields_list}\n\n"
        f"Generate one question per missing field."
    )


def _translate_question_prompt(question_en: str, target_language_name: str) -> str:
    return (
        f"Translate the following question into {target_language_name}.\n"
        f"Return ONLY the translated question text, nothing else.\n\n"
        f"Question: {question_en}"
    )


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _call_gemini_text(prompt: str, config: Config) -> str:
    import google.generativeai as genai  # type: ignore[import]

    genai.configure(api_key=config.google_api_key)
    model = genai.GenerativeModel(
        model_name=config.gemini_model,
        generation_config=genai.GenerationConfig(temperature=0.2),
    )
    response = model.generate_content(prompt)
    return response.text.strip()


def _call_openai_text(prompt: str, config: Config) -> str:
    from openai import OpenAI  # type: ignore[import]

    client = OpenAI(api_key=config.openai_api_key)
    response = client.chat.completions.create(
        model=config.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip()


def _call_llm_text(prompt: str, config: Config) -> str:
    provider = config.get_llm_provider()
    if provider == "gemini":
        return _call_gemini_text(prompt, config)
    return _call_openai_text(prompt, config)


def _call_llm_json(system: str, user: str, config: Config) -> str:
    provider = config.get_llm_provider()
    if provider == "gemini":
        import google.generativeai as genai  # type: ignore[import]

        genai.configure(api_key=config.google_api_key)
        model = genai.GenerativeModel(
            model_name=config.gemini_model,
            system_instruction=system,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return model.generate_content(user).text
    else:
        from openai import OpenAI  # type: ignore[import]

        client = OpenAI(api_key=config.openai_api_key)
        response = client.chat.completions.create(
            model=config.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return response.choices[0].message.content or ""


# ── Main class ────────────────────────────────────────────────────────────────

class FollowUpGenerator:
    """Identify missing product fields and generate questions for the artisan.

    Parameters
    ----------
    config:
        Pipeline configuration.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    # ── Missing field detection ────────────────────────────────────────────────

    def identify_missing_fields(self, facts: ProductFacts) -> list[str]:
        """Return list of field names that are missing but expected for the category.

        Parameters
        ----------
        facts:
            Extracted product facts.

        Returns
        -------
        list[str]
            Names of fields that are ``None`` but important for this category.
        """
        category = facts.get_category_str()
        required = CATEGORY_REQUIRED_FIELDS.get(
            category, CATEGORY_REQUIRED_FIELDS["default"]
        )

        missing: list[str] = []
        for field_name in required:
            field_value = getattr(facts, field_name, None)
            if field_value is None:
                missing.append(field_name)
            elif hasattr(field_value, "status") and field_value.status == "missing":
                missing.append(field_name)

        logger.info(
            "Category '%s': %d missing fields: %s", category, len(missing), missing
        )
        return missing

    # ── Question generation ────────────────────────────────────────────────────

    def generate_questions(
        self,
        facts: ProductFacts,
        language_code: str = "en",
        language_name: str = "English",
    ) -> list[FollowUpQuestion]:
        """Generate follow-up questions for missing fields.

        Parameters
        ----------
        facts:
            Extracted product facts.
        language_code:
            ISO 639-1 code of the artisan's detected language.
        language_name:
            Human-readable language name for the local translation prompt.

        Returns
        -------
        list[FollowUpQuestion]
        """
        missing_fields = self.identify_missing_fields(facts)
        if not missing_fields:
            logger.info("No missing fields — no follow-up questions needed.")
            return []

        product_name_field = facts.product_name
        product_name = (
            product_name_field.value
            if product_name_field and isinstance(product_name_field.value, str)
            else ""
        )

        # Step 1: Generate English questions
        raw = _call_llm_json(
            _questions_system_prompt(),
            _questions_user_prompt(missing_fields, product_name),
            self.config,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = "\n".join(l for l in raw.splitlines() if not l.startswith("```"))

        try:
            questions_data: list[dict] = json.loads(raw)
            if isinstance(questions_data, dict):
                # Some models wrap the array in an object
                questions_data = questions_data.get(
                    "questions", list(questions_data.values())[0]
                )
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse questions JSON: %s\nRaw: %s", exc, raw)
            return []

        questions: list[FollowUpQuestion] = []
        for item in questions_data:
            field = item.get("field", "")
            q_en = item.get("question_en", "")
            if not field or not q_en:
                continue

            # Step 2: Translate to artisan's language (skip if already English)
            q_local = ""
            if language_code and language_code != "en":
                try:
                    q_local = self._translate_to_local(q_en, language_name)
                except Exception as exc:
                    logger.warning("Local question translation failed: %s", exc)

            questions.append(
                FollowUpQuestion(field=field, question_en=q_en, question_local=q_local)
            )

        logger.info("Generated %d follow-up question(s).", len(questions))
        return questions

    def _translate_to_local(self, question_en: str, language_name: str) -> str:
        prompt = _translate_question_prompt(question_en, language_name)
        return _call_llm_text(prompt, self.config)
