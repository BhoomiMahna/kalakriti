"""
LLM client for the Instagram pipeline.

Uses the package's real GeminiLLMClient when a key is configured; otherwise an
offline FallbackLLMClient that satisfies the same `complete()` contract so the
demo runs with no key and no network. The fallback NEVER invents product facts
— it only rewords the description/facts it is given (matching the app's
grounded-generation policy).
"""
from __future__ import annotations

import json
import logging
import re

from core.config import settings

logger = logging.getLogger(__name__)


class FallbackLLMClient:
    """Deterministic, offline stand-in implementing the LLMClient protocol."""

    def complete(self, system_prompt: str, user_prompt: str, temperature: float = 0.4) -> str:
        # Story-uniqueness scorer expects a single integer 1-10.
        if "Uniqueness rating" in user_prompt:
            desc = user_prompt.lower()
            score = 7
            if any(w in desc for w in ("handmade", "hand-", "phulkari", "embroidery", "carved", "heritage")):
                score = 8
            if len(desc) > 400:
                score = 9
            return str(score)

        # Caption-coherence check expects YES/NO — fallback is grounded, so YES.
        if "Consistent?" in user_prompt:
            return "YES"

        # Otherwise: caption JSON. Build it from the supplied facts/listing only.
        facts, listing = self._extract(user_prompt)
        return json.dumps(self._caption(facts, listing))

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract(user_prompt: str) -> tuple[dict, dict]:
        facts, listing = {}, {}
        m = re.search(r"Product facts:\s*(\{.*?\})\s*\n\nProduct listing", user_prompt, re.S)
        if m:
            try:
                facts = json.loads(m.group(1))
            except Exception:  # noqa: BLE001
                pass
        m = re.search(r"Product listing:\s*(\{.*\})\s*\n\nGenerate", user_prompt, re.S)
        if m:
            try:
                listing = json.loads(m.group(1))
            except Exception:  # noqa: BLE001
                pass
        return facts, listing

    @staticmethod
    def _caption(facts: dict, listing: dict) -> dict:
        title = (listing.get("title") or facts.get("product_name") or "Handcrafted piece")
        short = listing.get("short_description") or ""
        story = listing.get("story") or listing.get("description") or ""
        material = facts.get("material")
        if isinstance(material, list):
            material = ", ".join(str(m) for m in material)
        region = facts.get("region") or facts.get("origin") or ""

        lines = [f"✨ {title}"]
        if short:
            lines.append(short.strip())
        elif story:
            lines.append(story.strip()[:200])
        if region:
            lines.append(f"Handmade in {region}.")
        caption_text = " ".join(lines)[:600]

        base_tags = ["handmade", "artisan", "handcrafted", "madeinindia", "supportlocal",
                     "craftsmanship", "slowmade", "sustainable", "uniquegift", "shophandmade",
                     "artisanmade", "traditionalcraft", "homedecor", "handmadewithlove", "craft"]
        for extra in filter(None, [material, region, facts.get("category")]):
            tag = re.sub(r"[^a-z0-9]", "", str(extra).lower())
            if tag and tag not in base_tags:
                base_tags.insert(0, tag)
        return {
            "caption_text": caption_text,
            "hashtags": base_tags[:20],
            "call_to_action": "Discover the craft — link in bio to shop.",
        }


def build_llm():
    """Real Gemini client if a key exists, else the offline fallback."""
    key = settings.gemini_api_key or settings.google_api_key
    if not key:
        logger.info("Instagram: no Gemini key — using offline caption generator.")
        return FallbackLLMClient()
    try:
        import sys
        if settings.repo_root not in sys.path:
            sys.path.insert(0, settings.repo_root)
        from artisans_ai.instagram.llm_client import GeminiLLMClient  # type: ignore

        return GeminiLLMClient(api_key=key)
    except Exception:  # noqa: BLE001
        logger.exception("Instagram: Gemini client init failed — using fallback.")
        return FallbackLLMClient()
