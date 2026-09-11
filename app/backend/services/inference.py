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
) -> dict[str, Any]:
    """Return {category, material, size_bucket, complexity_score, material_cost_inr}."""
    text = text or ""
    facts = facts or {}

    category = _first_match(text, _CATEGORY_KEYWORDS)
    if category and known_categories and category not in known_categories:
        category = None
    if not category:
        category = (known_categories or ["Terracotta_Pottery"])[0]

    material = _first_match(text, _MATERIAL_KEYWORDS)
    if material and known_materials and material not in known_materials:
        material = None
    if not material:
        # try product facts, then a category-typical default
        fmat = facts.get("material")
        if isinstance(fmat, list) and fmat:
            material = _first_match(" ".join(fmat), _MATERIAL_KEYWORDS)
        material = material or (known_materials or ["Cotton"])[0]

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
    }
