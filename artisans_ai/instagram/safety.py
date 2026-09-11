"""Content safety checks run immediately before publishing."""

from __future__ import annotations

import logging
import re

import cv2
import numpy as np

from .config import InstagramConfig
from .instagram_schema import ContentSafetyResult, InstagramCaption
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

# Same pattern as your existing FactualValidator forbidden-terms list --
# replace/extend with your real moderation term list.
FORBIDDEN_TERMS = [
    "guaranteed cure",
    "100% authentic" ,  # unverifiable superlative claim
    "best in the world",
    "miracle",
]

MISLEADING_PATTERNS = [
    r"\bfree\b.*\bshipping\b.*\bworldwide\b",  # example: unverified blanket claim
]


class ContentSafetyChecker:
    def __init__(self, config: InstagramConfig, llm_client: LLMClient):
        self.config = config
        self.llm_client = llm_client

    # ── Image safety ────────────────────────────────────────────────────

    def check_images(self, image_paths: list[str]) -> tuple[bool, list[str]]:
        flags = []
        for path in image_paths:
            img = cv2.imread(path)
            if img is None:
                flags.append(f"Unreadable image: {path}")
                continue

            height, width = img.shape[:2]
            if min(width, height) < self.config.ig_min_resolution_px:
                flags.append(f"{path}: below minimum resolution ({width}x{height})")

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if blur_score < self.config.ig_blur_threshold_safety:
                flags.append(f"{path}: fails stricter pre-publish blur check ({blur_score:.1f})")

            # Basic pixel variance check -- catches near-solid-color / corrupt images
            pixel_std = float(np.std(img))
            if pixel_std < 5.0:
                flags.append(f"{path}: suspiciously low pixel variance ({pixel_std:.2f}), possibly blank/corrupt")

        return (len(flags) == 0, flags)

    # ── Text safety ─────────────────────────────────────────────────────

    def check_text(self, caption: InstagramCaption) -> tuple[bool, list[str]]:
        flags = []
        text_lower = caption.full_text.lower()

        for term in FORBIDDEN_TERMS:
            if term in text_lower:
                flags.append(f"Forbidden term found: '{term}'")

        for pattern in MISLEADING_PATTERNS:
            if re.search(pattern, text_lower):
                flags.append(f"Potentially misleading claim matched pattern: {pattern}")

        if caption.character_count > 2200:
            flags.append(f"Caption exceeds Instagram's 2200 character limit ({caption.character_count})")

        if len(caption.hashtags) > 30:
            flags.append(f"Too many hashtags ({len(caption.hashtags)}), Instagram caps at 30")

        return (len(flags) == 0, flags)

    # ── Caption-image coherence (LLM) ───────────────────────────────────

    COHERENCE_PROMPT = (
        "You are checking whether a social media caption accurately describes "
        "a product, based only on the product description/facts provided "
        "(you cannot see the actual image, so judge textual consistency: does "
        "the caption reference the same type of product, materials, or "
        "features as the product facts?). "
        "Respond with ONLY 'YES' if consistent or 'NO' if there's a clear "
        "mismatch, nothing else."
    )

    def check_caption_coherence(self, caption: InstagramCaption, product_facts: dict) -> tuple[bool, list[str]]:
        user_prompt = (
            f"Caption:\n{caption.full_text}\n\n"
            f"Product facts:\n{product_facts}\n\n"
            "Consistent? (YES/NO):"
        )
        try:
            raw = self.llm_client.complete(self.COHERENCE_PROMPT, user_prompt, temperature=0.0)
        except NotImplementedError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Coherence check LLM call failed, failing open with a flag: %s", exc)
            return True, ["Coherence check could not run (LLM error) -- manual review recommended."]

        is_coherent = raw.strip().upper().startswith("YES")
        flags = [] if is_coherent else ["LLM flagged caption as inconsistent with product facts."]
        return is_coherent, flags

    # ── Orchestration ───────────────────────────────────────────────────

    def check(
        self,
        image_paths: list[str],
        caption: InstagramCaption,
        product_facts: dict,
    ) -> ContentSafetyResult:
        all_flags: list[str] = []

        images_safe, image_flags = self.check_images(image_paths)
        all_flags.extend(image_flags)

        text_safe, text_flags = self.check_text(caption)
        all_flags.extend(text_flags)

        coherent, coherence_flags = self.check_caption_coherence(caption, product_facts)
        all_flags.extend(coherence_flags)

        safe = images_safe and text_safe and coherent

        return ContentSafetyResult(
            safe=safe,
            flags=all_flags,
            details={
                "images_safe": images_safe,
                "text_safe": text_safe,
                "caption_coherent": coherent,
            },
        )
