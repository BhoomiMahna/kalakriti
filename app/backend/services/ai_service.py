"""
AI service — the single entry point the orchestrator uses for the language
pipeline (STT → translation → extraction → description → validation).

Two backends behind one interface (spec §20 "clean interfaces around each
model, easy replacement"):

* REAL: ``artisan_ai.ArtisanProductPipeline`` (Whisper/Bhashini/Sarvam ASR,
  IndicTrans2 translation, Gemini extraction+generation+validation). Enabled
  when ENABLE_AI_PIPELINE=true and the package + keys are available.

* FALLBACK: a deterministic, grounded generator that runs with no GPU and no
  external keys, producing the exact same output dict shape. It never invents
  materials, certifications, or cultural claims (spec §9 rule) — it only uses
  what the artisan actually provided.
"""
from __future__ import annotations

import logging
import re
import sys
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    def __init__(self) -> None:
        self._pipeline = None
        self._real = False
        if settings.enable_ai_pipeline:
            self._try_load_real_pipeline()

    def _try_load_real_pipeline(self) -> None:
        try:
            if settings.artisan_ai_root not in sys.path:
                sys.path.insert(0, settings.artisan_ai_root)
            from artisan_ai import ArtisanProductPipeline  # type: ignore

            self._pipeline = ArtisanProductPipeline()
            self._real = True
            logger.info("Real artisan_ai pipeline loaded.")
        except Exception:  # noqa: BLE001
            logger.exception("Could not load artisan_ai pipeline — using fallback generator")
            self._real = False

    @property
    def mode(self) -> str:
        if self._real:
            return "artisan_ai"
        from services.sarvam_service import get_sarvam_service
        return "sarvam" if get_sarvam_service().available else "fallback"

    # ── Public API ────────────────────────────────────────────────────────────

    def process(
        self,
        *,
        audio_path: str | None,
        text_hint: str = "",
        product_name: str = "",
        category: str = "",
        material: str = "",
        dimensions: str = "",
        artisan_name: str = "",
        region: str = "",
        language: str = "en",
    ) -> dict[str, Any]:
        """Return the canonical AI output dict (see pipeline._build_output)."""
        if self._real and audio_path:
            try:
                return self._pipeline.process(audio_path)
            except Exception:  # noqa: BLE001
                logger.exception("Real pipeline failed at runtime — using fallback")

        # Real STT via Sarvam: transcribe + translate the voice note to English.
        transcript_original = ""
        stt_model = "fallback"
        if audio_path:
            from services.sarvam_service import get_sarvam_service

            sarvam = get_sarvam_service()
            if sarvam.available:
                res = sarvam.transcribe_translate(audio_path)
                if res:
                    text_hint = res["text"] if not text_hint else f"{res['text']} {text_hint}"
                    transcript_original = res["text"]
                    language = res["language_code"] or language
                    stt_model = "sarvam"
                    logger.info("Sarvam STT: %s (%s)", res["text"][:60], res["language_name"])

        out = self._fallback(
            text_hint=text_hint,
            product_name=product_name,
            category=category,
            material=material,
            dimensions=dimensions,
            artisan_name=artisan_name,
            region=region,
            language=language,
        )
        out["transcription"] = {
            "original": transcript_original or text_hint,
            "asr_model": stt_model,
        }
        return out

    # ── Fallback generator ──────────────────────────────────────────────────────

    def _fallback(
        self,
        *,
        text_hint: str,
        product_name: str,
        category: str,
        material: str,
        dimensions: str,
        artisan_name: str,
        region: str,
        language: str,
    ) -> dict[str, Any]:
        text = (text_hint or "").strip()
        name = product_name.strip() or self._guess_name(text) or "Handcrafted Product"

        materials = self._split(material) or self._find_materials(text)
        colors = self._find_colors(text)

        facts = {
            "product_name": name,
            "category": category or None,
            "subcategory": None,
            "material": materials or None,
            "colors": colors or None,
            "dimensions": dimensions or None,
            "weight": None,
            "craft_type": "Handmade" if re.search(r"\bhand", text, re.I) else None,
            "craft_technique": None,
            "production_method": None,
            "region": region or None,
            "production_time": self._find_time(text),
            "usage": None,
            "cultural_significance": None,
            "care_instructions": None,
        }

        listing = self._build_listing(name, category, materials, colors, dimensions, text)
        story = self._build_story(name, artisan_name, region, materials, text)

        # Missing-field detection + simple follow-ups (grounded, non-fabricating).
        missing = [k for k in ("material", "dimensions", "usage", "care_instructions")
                   if not facts.get(k)]
        follow_ups = [{
            "field": f,
            "question_en": self._question_for(f),
            "question_local": "",
        } for f in missing[:4]]

        return {
            "language": {"code": language, "name": language, "confidence": 1.0,
                         "detection_source": "fallback"},
            "transcription": {"original": text, "asr_model": "fallback"},
            "translation": {"english": text, "model": "passthrough"},
            "product_facts": {k: v for k, v in facts.items()},
            "product_facts_with_evidence": {},
            "missing_fields": missing,
            "follow_up_questions": follow_ups,
            "listing": listing,
            "story": story,
            "validation": {"valid": True, "unsupported_claims": [],
                           "notes": "Fallback generator uses only artisan-provided facts."},
        }

    # ── Small heuristics (deliberately conservative — never invent facts) ───────

    @staticmethod
    def _split(value: str) -> list[str]:
        return [v.strip() for v in re.split(r"[,/&]| and ", value or "") if v.strip()]

    @staticmethod
    def _clean_narrative(text: str) -> str:
        """Drop sentences about internal cost/pricing — not buyer-facing copy."""
        sentences = re.split(r"(?<=[.!?])\s+", text or "")
        kept = [
            s for s in sentences
            if not re.search(r"cost|rupees?|₹|\brs\.?\b|price|रुपये|रुपए|कीमत|दाम", s, re.I)
        ]
        return " ".join(kept).strip()

    @staticmethod
    def _guess_name(text: str) -> str:
        m = re.search(r"\bthis is (?:a |an |my )?([A-Za-z][\w \-]{2,40})", text, re.I)
        return m.group(1).strip().title() if m else ""

    _KNOWN_MATERIALS = [
        "cotton", "silk", "wool", "jute", "bamboo", "cane", "brass", "clay",
        "terracotta", "wood", "sheesham", "rosewood", "khadi", "linen", "leather",
        "grass", "metal", "muslin",
    ]
    _KNOWN_COLORS = [
        "red", "blue", "green", "yellow", "black", "white", "pink", "orange",
        "purple", "brown", "gold", "silver", "maroon", "beige", "grey", "gray",
    ]

    def _find_materials(self, text: str) -> list[str]:
        t = (text or "").lower()
        return [m.title() for m in self._KNOWN_MATERIALS if m in t]

    def _find_colors(self, text: str) -> list[str]:
        t = (text or "").lower()
        return [c.title() for c in self._KNOWN_COLORS if re.search(rf"\b{c}\b", t)]

    @staticmethod
    def _find_time(text: str) -> str | None:
        m = re.search(r"(\d+\s*(?:day|days|week|weeks|hour|hours|month|months))", text or "", re.I)
        return m.group(1) if m else None

    @staticmethod
    def _question_for(field: str) -> str:
        return {
            "material": "What material is your product made from?",
            "dimensions": "What is the size or dimensions of your product?",
            "usage": "How is this product used?",
            "care_instructions": "How should the buyer care for or clean it?",
        }.get(field, f"Can you tell us more about the {field.replace('_', ' ')}?")

    def _build_listing(self, name, category, materials, colors, dimensions, text) -> dict[str, Any]:
        mat = ", ".join(materials) if materials else ""
        col = ", ".join(colors) if colors else ""
        # Build a title but never repeat a word already present in the name
        # (e.g. avoid "Terracotta Terracotta Vase").
        name_words = {w.lower() for w in re.findall(r"\w+", name)}
        lead = [t for t in (colors + materials) if t.lower() not in name_words]
        title = " ".join([*lead, name])[:80] or name

        short_bits = [f"Handcrafted {name.lower()}"]
        if mat:
            short_bits.append(f"made from {mat.lower()}")
        short = (", ".join(short_bits)).capitalize()[:150]

        paras = []
        lead = f"This {name.lower()} is a handcrafted piece"
        if mat:
            lead += f" made from {mat.lower()}"
        if col:
            lead += f", finished in {col.lower()}"
        lead += "."
        paras.append(lead)
        narrative = self._clean_narrative(text)
        if narrative:
            paras.append(narrative)
        if dimensions:
            paras.append(f"Approximate size: {dimensions}.")
        description = "\n\n".join(paras)

        highlights = []
        if mat:
            highlights.append(f"Made from {mat}")
        if col:
            highlights.append(f"Colour: {col}")
        if dimensions:
            highlights.append(f"Size: {dimensions}")
        highlights.append("Handcrafted by an independent artisan")

        keywords = [k for k in ([name] + materials + colors + ([category] if category else [])) if k]

        return {
            "title": title,
            "short_description": short,
            "description": description,
            "highlights": highlights[:6],
            "keywords": list(dict.fromkeys(keywords))[:12],
        }

    @staticmethod
    def _build_story(name, artisan_name, region, materials, text) -> str:
        parts = []
        maker = artisan_name.strip() or "an independent artisan"
        origin = f" from {region}" if region else ""
        parts.append(f"This {name.lower()} was made by {maker}{origin}.")
        if materials:
            parts.append(f"It is crafted using {', '.join(materials).lower()}.")
        narrative = AIService._clean_narrative(text)
        if narrative:
            parts.append(narrative)
        return " ".join(parts)


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
