"""
artisan_ai.evaluation.description_eval
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Description generation evaluation.

Metrics
-------
- Unsupported claim rate (primary — factual accuracy)
- Fact coverage (how many available facts appear in the description)
- ROUGE-L for readability baseline

The factual accuracy metrics are more important than ROUGE-L.
ROUGE-L is a heuristic and should only be used as a secondary signal.

Example::

    from artisan_ai.evaluation.description_eval import DescriptionEvaluator
    from artisan_ai.extraction.product_schema import ProductFacts, ProductListing

    evaluator = DescriptionEvaluator()
    results = evaluator.evaluate(
        facts=facts,
        listing=listing,
        unsupported_claims=validation.unsupported_claims,
        reference_description="...",  # Optional
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from artisan_ai.extraction.product_schema import ProductFacts, ProductListing

logger = logging.getLogger(__name__)


@dataclass
class DescriptionEvalResult:
    unsupported_claim_count: int
    unsupported_claim_rate: float   # unsupported / total_sentences
    fact_coverage: float            # fraction of non-null facts mentioned
    rouge_l: float | None = None    # None if no reference provided
    total_sentences: int = 0
    covered_facts: list[str] | None = None


class DescriptionEvaluator:
    """Evaluate the quality of generated product descriptions."""

    def evaluate(
        self,
        facts: ProductFacts,
        listing: ProductListing,
        unsupported_claims: list[str],
        reference_description: str | None = None,
    ) -> DescriptionEvalResult:
        """Evaluate a generated listing.

        Parameters
        ----------
        facts:
            The structured product facts used for generation.
        listing:
            The generated product listing.
        unsupported_claims:
            List of unsupported claims from :class:`FactualValidator`.
        reference_description:
            Optional human-written reference description for ROUGE-L.
        """
        full_text = " ".join(
            [
                listing.title,
                listing.short_description,
                listing.description,
                " ".join(listing.highlights),
            ]
        )

        # ── Sentence count ─────────────────────────────────────────────────────
        import re
        sentences = re.split(r"[.!?]+", full_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        total_sentences = len(sentences)

        # ── Unsupported claim rate ─────────────────────────────────────────────
        unsupported_count = len(unsupported_claims)
        unsupported_rate = (
            unsupported_count / total_sentences if total_sentences > 0 else 0.0
        )

        # ── Fact coverage ──────────────────────────────────────────────────────
        flat_facts = facts.to_flat_dict()
        non_null_fields = {
            k: v for k, v in flat_facts.items() if v is not None
        }
        covered: list[str] = []
        full_text_lower = full_text.lower()

        for field_name, value in non_null_fields.items():
            if isinstance(value, list):
                if any(str(v).lower() in full_text_lower for v in value):
                    covered.append(field_name)
            elif isinstance(value, str):
                if value.lower() in full_text_lower:
                    covered.append(field_name)

        fact_coverage = (
            len(covered) / len(non_null_fields) if non_null_fields else 0.0
        )

        # ── ROUGE-L (optional) ────────────────────────────────────────────────
        rouge_l: float | None = None
        if reference_description:
            rouge_l = self._rouge_l(
                reference=reference_description,
                hypothesis=listing.description,
            )

        result = DescriptionEvalResult(
            unsupported_claim_count=unsupported_count,
            unsupported_claim_rate=round(unsupported_rate, 4),
            fact_coverage=round(fact_coverage, 4),
            rouge_l=round(rouge_l, 4) if rouge_l is not None else None,
            total_sentences=total_sentences,
            covered_facts=covered,
        )

        logger.info(
            "Description Eval — Unsupported: %d (%.4f), "
            "Coverage: %.4f, ROUGE-L: %s",
            result.unsupported_claim_count,
            result.unsupported_claim_rate,
            result.fact_coverage,
            result.rouge_l,
        )
        return result

    @staticmethod
    def _rouge_l(reference: str, hypothesis: str) -> float:
        try:
            from rouge_score import rouge_scorer  # type: ignore[import]

            scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
            scores = scorer.score(reference, hypothesis)
            return scores["rougeL"].fmeasure
        except ImportError:
            logger.warning(
                "rouge-score not installed. Install with: pip install rouge-score"
            )
            return 0.0
