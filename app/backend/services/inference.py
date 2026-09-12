"""
Infer pricing-model inputs from what the artisan *said* (and product facts),
so the artisan never has to read or fill an English form.

Maps free speech (English / Hinglish / common Hindi craft words) onto the
pricing model's known category / material / size vocabulary. Everything has a
sensible default, and the artisan can always adjust the final price on review.
"""
from __future__ import annotations

import re
from typing import Any

# ── Category detection ───────────────────────────────────────────────────────
# keyword (lowercased, incl. common Hindi/Hinglish) -> pricing-model category
_CATEGORY_KEYWORDS: list[tuple[list[str], str]] = [
    (["dupatta", "chunni", "odhni", "दुपट्टा", "chunari"], "BlockPrint_Dupatta"),
    (["saree", "sari", "साड़ी"], "BlockPrint_Saree"),
    (["kurta", "kurti", "kameez", "कुर्ता", "shirt", "tunic"], "Embroidery_Handloom_Kurta"),
    (["basket", "tokri", "टोकरी", "cane basket"], "Bamboo_Cane_Basket"),
    (["jute bag", "bag", "थैला", "jhola", "tote"], "Jute_Bag"),
    (["pot", "pottery", "vase", "matka", "diya", "मिट्टी", "मटका", "terracotta",
      "clay", "earthen"], "Terracotta_Pottery"),
    (["brass", "metal", "dhokra", "bell metal", "पीतल", "idol", "murti", "मूर्ति"],
     "Brass_Metal_Handicraft"),
    (["wood", "wooden", "carved", "carving", "लकड़ी", "sheesham", "rosewood",
      "elephant", "showpiece"], "Wooden_Handicraft"),
]

# ── Material detection ───────────────────────────────────────────────────────
# spoken word -> exact pricing-model material label
_MATERIAL_KEYWORDS: list[tuple[list[str], str]] = [
    (["cotton", "सूती", "cotton fabric"], "Cotton"),
    (["khadi", "खादी"], "Khadi"),
    (["muslin", "मलमल"], "Muslin"),
    (["chanderi"], "Chanderi Silk"),
    (["kota"], "Kota Doria"),
    (["modal"], "Modal Silk"),
    (["cotton silk"], "Cotton Silk"),
    (["silk", "रेशम"], "Modal Silk"),
    (["jute", "जूट"], "Jute"),
    (["bamboo", "बांस"], "Bamboo"),
    (["cane", "बेंत"], "Cane"),
    (["kauna"], "Kauna Grass"),
    (["sabai"], "Sabai Grass"),
    (["grass", "घास"], "Kauna Grass"),
    (["brass", "पीतल"], "Brass"),
    (["bell metal"], "Bell Metal"),
    (["dhokra"], "Dhokra Metal"),
    (["terracotta"], "Terracotta"),
    (["glazed"], "Glazed Clay"),
    (["clay", "mitti", "मिट्टी"], "Clay"),
    (["sheesham", "शीशम"], "Sheesham Wood"),
    (["rosewood", "शीशम की लकड़ी"], "Rosewood"),
    (["mango wood", "आम की लकड़ी"], "Mango Wood"),
    (["whitewood", "wood", "wooden", "लकड़ी"], "Whitewood"),
]

# ── Craft/category HINT mapping ──────────────────────────────────────────────
# Maps the product's already-known craft/category (from onboarding or the form,
# e.g. "Textile", "Pottery", "Bag") onto a pricing-model category. Used ONLY as a
# hint when the spoken text has no recognizable item keyword — so a real product
# is not blindly defaulted to the alphabetically-first (cheapest) pricing class.
_CRAFT_TO_PRICING: list[tuple[list[str], str]] = [
    (["pottery", "terracotta", "clay", "ceramic", "मिट्टी"], "Terracotta_Pottery"),
    (["dupatta", "chunni", "stole", "scarf", "odhni"], "BlockPrint_Dupatta"),
    (["saree", "sari", "साड़ी"], "BlockPrint_Saree"),
    (["kurta", "kurti", "kameez", "shirt", "tunic", "apparel", "clothing",
      "garment", "textile", "fabric", "handloom", "cloth", "embroidery"],
     "Embroidery_Handloom_Kurta"),
    (["bag", "tote", "sling", "purse", "pouch", "jhola", "थैला"], "Jute_Bag"),
    (["basket", "tokri", "टोकरी"], "Bamboo_Cane_Basket"),
    (["brass", "metal", "dhokra", "bell metal", "idol", "murti", "पीतल"],
     "Brass_Metal_Handicraft"),
    (["wood", "wooden", "furniture", "carving", "sheesham", "rosewood", "लकड़ी"],
     "Wooden_Handicraft"),
]

_SIZE_KEYWORDS: list[tuple[list[str], str]] = [
    (["large", "big", "bada", "बड़ा", "huge", "tall"], "Large"),
    (["small", "chota", "छोटा", "tiny", "mini"], "Small"),
    (["medium", "madhyam", "मध्यम"], "Medium"),
]

# Rough per-category default material cost (INR) when the artisan doesn't say one.
_DEFAULT_COST: dict[str, float] = {
    "BlockPrint_Dupatta": 150,
    "BlockPrint_Saree": 400,
    "Embroidery_Handloom_Kurta": 300,
    "Bamboo_Cane_Basket": 80,
    "Jute_Bag": 90,
    "Terracotta_Pottery": 100,
    "Brass_Metal_Handicraft": 500,
    "Wooden_Handicraft": 600,
}


def _first_match(text: str, table: list[tuple[list[str], str]]) -> str | None:
    t = text.lower()
    for keywords, value in table:
        for kw in keywords:
            if kw in t:
                return value
    return None


def _find_cost(text: str) -> float | None:
    """Pull a material cost the artisan mentioned, e.g. '200 rupees', '₹150'."""
    m = re.search(r"(?:₹|rs\.?\s*|rupees?\s*)(\d{2,6})", text, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d{2,6})\s*(?:rupees?|rs\.?|₹|रुपये|रुपए)", text, re.I)
    if m:
        return float(m.group(1))
    return None


def infer_pricing_inputs(
    text: str,
    facts: dict[str, Any] | None,
    known_categories: list[str],
    known_materials: list[str],
    category_hint: str = "",
    material_hint: str = "",
) -> dict[str, Any]:
    """Return the pricing-model input vector plus a confidence signal.

    Keys: {category, material, size_bucket, complexity_score, material_cost_inr,
           category_source, confidence}.

    ``confidence`` is "high" when the category came from a real signal (the
    spoken text or the product's known craft), and "low" when nothing could be
    determined. A "low" result means callers must NOT present the resulting price
    as a confident recommendation — otherwise every unclassifiable product would
    collapse onto the same cheapest-category price (the ₹260 bug).
    """
    text = text or ""
    facts = facts or {}

    # 1) Category from the spoken text (strongest signal).
    category = _first_match(text, _CATEGORY_KEYWORDS)
    category_source = "text" if category else None

    # 2) Fall back to the product's KNOWN craft/category (onboarding/form/facts),
    #    mapped into the pricing vocabulary — not the alphabetically-first class.
    if not category:
        fcat = facts.get("category")
        hint = " ".join(filter(None, [category_hint, fcat if isinstance(fcat, str) else ""]))
        if hint:
            category = _first_match(hint, _CATEGORY_KEYWORDS) or _first_match(hint, _CRAFT_TO_PRICING)
            if category:
                category_source = "hint"

    if category and known_categories and category not in known_categories:
        category = None
        category_source = None

    confidence = "high" if category else "low"
    if not category:
        # No real signal. Pick a neutral mid default only so the model can still
        # produce a rough estimate; confidence="low" tells the caller not to
        # present it as a recommendation or store a fake price.
        category = "Terracotta_Pottery" if (not known_categories or
                    "Terracotta_Pottery" in known_categories) else known_categories[0]
        category_source = "default"

    # Material: text -> hint -> facts -> category-typical default.
    material = _first_match(text, _MATERIAL_KEYWORDS)
    if not material and material_hint:
        material = _first_match(material_hint, _MATERIAL_KEYWORDS)
    if not material:
        fmat = facts.get("material")
        if isinstance(fmat, list) and fmat:
            material = _first_match(" ".join(fmat), _MATERIAL_KEYWORDS)
        elif isinstance(fmat, str):
            material = _first_match(fmat, _MATERIAL_KEYWORDS)
    if material and known_materials and material not in known_materials:
        material = None
    if not material:
        material = (known_materials or ["Cotton"])[0]

    size = _first_match(text, _SIZE_KEYWORDS) or "Medium"

    cost = _find_cost(text)
    if cost is None:
        cost = _DEFAULT_COST.get(category, 150)

    # crude complexity: more descriptive detail / "intricate" words => higher
    complexity = 3
    if re.search(r"intricate|detailed|fine work|बारीक|complex|elaborate", text, re.I):
        complexity = 5
    elif re.search(r"simple|plain|basic|सादा", text, re.I):
        complexity = 2

    return {
        "category": category,
        "material": material,
        "size_bucket": size,
        "complexity_score": complexity,
        "material_cost_inr": cost,
        "category_source": category_source,
        "confidence": confidence,
    }
