"""
Pricing service — wraps the provided ``pricing_model.pkl``.

Interface mirrors the ``suggest_price`` function from the project's
Dynamic Pricing notebook:

    inputs  -> category, material, size_bucket, complexity_score,
               material_cost_inr, description
    output  -> {price, low, high, reasoning, model_price, cost_floor, comparables}

The comparable-listings step (sentence-transformers) is optional: if the
reference embeddings/CSV are not present it is skipped gracefully, and the
suggestion falls back to model prediction + a category cost floor.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

# Minimum markup multipliers by category (from the notebook).
MIN_MARKUP_BY_CATEGORY: dict[str, float] = {
    "Terracotta_Pottery": 2.0,
    "BlockPrint_Dupatta": 2.5,
    "BlockPrint_Saree": 2.5,
    "Bamboo_Cane_Basket": 2.0,
    "Brass_Metal_Handicraft": 2.0,
    "Wooden_Handicraft": 2.0,
    "Jute_Bag": 2.5,
    "Embroidery_Handloom_Kurta": 2.5,
}


class PricingService:
    def __init__(self) -> None:
        self._model = None
        self._metadata: dict[str, list[str]] = {}
        self._embedder = None
        self._ref_df = None
        self._ref_embeddings = None
        self._load()

    def _load(self) -> None:
        path = Path(settings.pricing_model_path)
        if not path.exists():
            logger.warning("pricing_model.pkl not found at %s — using heuristic pricing", path)
            return
        try:
            import joblib

            self._model = joblib.load(path)
            logger.info("Pricing model loaded from %s", path)
            self._read_known_values()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to load pricing model — using heuristic pricing")

        # Optional: comparable listings via sentence-transformers.
        try:
            csv_path = Path(settings.pricing_reference_csv)
            emb_path = Path(settings.pricing_reference_embeddings)
            if csv_path.exists() and emb_path.exists():
                import numpy as np
                import pandas as pd
                from sentence_transformers import SentenceTransformer

                self._ref_df = pd.read_csv(csv_path)
                self._ref_embeddings = np.load(emb_path)
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Comparable-listing search enabled (%d refs)", len(self._ref_df))
        except Exception:  # noqa: BLE001
            logger.info("Comparable-listing search unavailable — skipping (optional)")

    def _read_known_values(self) -> None:
        """Introspect the OneHotEncoder to expose valid dropdown values."""
        try:
            ohe = self._model.named_steps["preprocess"].named_transformers_["cat"]
            cats = ohe.categories_
            self._metadata = {
                "categories": sorted(cats[0].tolist()),
                "size_buckets": sorted(cats[1].tolist()),
                "materials": sorted(cats[2].tolist()),
            }
        except Exception:  # noqa: BLE001
            self._metadata = {}

    @property
    def available(self) -> bool:
        return self._model is not None

    def metadata(self) -> dict[str, list[str]]:
        return self._metadata or {
            "categories": sorted(MIN_MARKUP_BY_CATEGORY.keys()),
            "size_buckets": ["Small", "Medium", "Large"],
            "materials": [],
        }

    def _comparables(self, description: str, top_k: int = 3) -> list[dict[str, Any]]:
        if not (self._embedder is not None and self._ref_embeddings is not None and description):
            return []
        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            q = self._embedder.encode([description], convert_to_numpy=True)
            sims = cosine_similarity(q, self._ref_embeddings)[0]
            top = np.argsort(sims)[::-1][:top_k]
            out = []
            for i in top:
                row = self._ref_df.iloc[int(i)]
                out.append({
                    "category": row.get("category"),
                    "description": str(row.get("description", ""))[:160],
                    "price_inr": float(row.get("price_inr", 0)),
                    "similarity": round(float(sims[i]), 3),
                })
            return out
        except Exception:  # noqa: BLE001
            return []

    def suggest(
        self,
        *,
        category: str,
        material: str,
        size_bucket: str,
        complexity_score: int,
        material_cost_inr: float,
        description: str = "",
    ) -> dict[str, Any]:
        model_price: float | None = None

        if self._model is not None:
            try:
                import pandas as pd

                x = pd.DataFrame([{
                    "complexity_score": complexity_score,
                    "material_cost_inr": material_cost_inr,
                    "category": category,
                    "size_bucket": size_bucket,
                    "material": material,
                }])
                model_price = float(self._model.predict(x)[0])
            except Exception:  # noqa: BLE001
                logger.exception("Pricing model prediction failed; falling back to heuristic")

        min_markup = MIN_MARKUP_BY_CATEGORY.get(category, 2.0)
        cost_floor = material_cost_inr * min_markup

        if model_price is None:
            # Heuristic when model unavailable: cost floor scaled by complexity.
            model_price = cost_floor * (1 + 0.12 * complexity_score)

        final_price = max(model_price, cost_floor)

        comparables = self._comparables(description)
        low = round(final_price * 0.88, -1)
        high = round(final_price * 1.12, -1)
        if comparables:
            comp_prices = [c["price_inr"] for c in comparables if c["price_inr"]]
            if comp_prices:
                low = round((low + min(comp_prices)) / 2, -1)
                high = round((high + max(comp_prices)) / 2, -1)

        reasoning = (
            f"Suggested price ₹{round(final_price):,}. "
            f"Model estimate ₹{round(model_price):,}; "
            f"cost floor ₹{round(cost_floor):,} "
            f"(material ₹{round(material_cost_inr):,} × {min_markup}× markup)."
        )
        if not self.available:
            reasoning += " (Heuristic estimate — pricing model not loaded.)"

        return {
            "price": round(final_price),
            "low": max(0, low),
            "high": high,
            "reasoning": reasoning,
            "model_price": round(model_price),
            "cost_floor": round(cost_floor),
            "comparables": comparables,
        }


_pricing_service: PricingService | None = None


def get_pricing_service() -> PricingService:
    global _pricing_service
    if _pricing_service is None:
        _pricing_service = PricingService()
    return _pricing_service
