"""Instagram caption + hashtag generation, following the DescriptionGenerator pattern."""

from __future__ import annotations

import json
import logging
import re

from .instagram_schema import InstagramCaption
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

SYSTEM_PROMPT = """You write Instagram captions for a handmade artisan marketplace.

Voice: warm, engaging, concise, a little storytelling flair. Use emoji sparingly \
and naturally (not one per line). Total caption body must stay under 2200 \
characters including hashtags.

You must respond with ONLY valid JSON, no markdown fences, no preamble, in \
exactly this shape:

{
  "caption_text": "the main caption body, 2-5 sentences, storytelling angle",
  "hashtags": ["list", "of", "15", "to", "25", "hashtags", "without", "the", "hash", "symbol"],
  "call_to_action": "one short line, e.g. 'Link in bio to shop' or 'DM to order'"
}

Hashtags should mix niche/craft-specific tags relevant to the product with a \
few broader, higher-traffic tags. Do not include the '#' character in the \
hashtags list itself."""


class InstagramCaptionGenerator:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def generate(self, product_facts: dict, listing: dict) -> InstagramCaption:
        user_prompt = (
            f"Product facts:\n{json.dumps(product_facts, default=str)}\n\n"
            f"Product listing:\n{json.dumps(listing, default=str)}\n\n"
            "Generate the Instagram caption JSON now."
        )

        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw = self.llm_client.complete(SYSTEM_PROMPT, user_prompt, temperature=0.6)
                parsed = self._parse(raw)
                return self._to_model(parsed)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "InstagramCaptionGenerator attempt %d/%d failed: %s",
                    attempt,
                    MAX_RETRIES,
                    exc,
                )

        raise RuntimeError(
            f"Failed to generate a valid Instagram caption after {MAX_RETRIES} attempts"
        ) from last_error

    @staticmethod
    def _parse(raw: str) -> dict:
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        data = json.loads(cleaned)
        for key in ("caption_text", "hashtags", "call_to_action"):
            if key not in data:
                raise ValueError(f"LLM response missing required key: {key}")
        return data

    @staticmethod
    def _to_model(data: dict) -> InstagramCaption:
        hashtags = [str(h).lstrip("#").strip() for h in data["hashtags"] if str(h).strip()]
        caption_text = str(data["caption_text"]).strip()
        cta = str(data["call_to_action"]).strip()

        full_text = f"{caption_text}\n\n{cta}\n\n" + " ".join(f"#{t}" for t in hashtags)
        if len(full_text) > 2200:
            # Trim hashtags first (cheapest to lose) until we fit.
            while hashtags and len(full_text) > 2200:
                hashtags.pop()
                full_text = f"{caption_text}\n\n{cta}\n\n" + " ".join(f"#{t}" for t in hashtags)

        return InstagramCaption(
            caption_text=caption_text,
            hashtags=hashtags,
            call_to_action=cta,
            character_count=len(full_text),
        )
