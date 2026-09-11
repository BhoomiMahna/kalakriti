"""
artisan_ai.evaluation.extraction_eval
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Product fact extraction evaluation.

Metrics
-------
- Field-level precision, recall, F1
- Hallucination rate (fields asserted but not in reference)
- Coverage rate (reference fields correctly extracted)

Example::

    from artisan_ai.evaluation.extraction_eval import ExtractionEvaluator

    evaluator = ExtractionEvaluator()
    results = evaluator.evaluate(
        reference_facts={
            "product_name": "Phulkari Dupatta",
            "material": ["Cotton"],
            "colors": ["Red", "Yellow"],
        },
        predicted_facts={
            "product_name": "Phulkari Dupatta",
            "material": ["Cotton"],
            "colors": ["Red", "Yellow"],
            "region": "Punjab",   # hallucinated – not in reference
        },
    )
    print(results)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExtractionEvalResult:
    precision: float
    recall: float
    f1: float
    hallucination_rate: float
    hallucinated_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    num_reference_fields: int = 0
    num_predicted_fields: int = 0


class ExtractionEvaluator:
    """Evaluate structured product fact extraction quality.

    Parameters
    ----------
    case_sensitive:
        If ``False`` (default), string values are compared
        case-insensitively.
    """

    def __init__(self, case_sensitive: bool = False) -> None:
        self.case_sensitive = case_sensitive

    def evaluate(
        self,
        reference_facts: dict,
        predicted_facts: dict,
    ) -> ExtractionEvalResult:
        """Compare predicted product facts against a reference.

        Parameters
        ----------
        reference_facts:
            Ground-truth product attributes (field → value or list of values).
            Fields with ``None`` values are treated as missing.
        predicted_facts:
            Extracted product attributes from the pipeline.
            Fields with ``None`` values are treated as not extracted.

        Returns
        -------
        ExtractionEvalResult
        """
        ref_present = {
            k: v for k, v in reference_facts.items() if v is not None
        }
        pred_present = {
            k: v for k, v in predicted_facts.items() if v is not None
        }

        ref_keys = set(ref_present.keys())
        pred_keys = set(pred_present.keys())

        # ── Field-level match ──────────────────────────────────────────────────
        true_positives: list[str] = []
        false_positives: list[str] = []  # hallucinated
        false_negatives: list[str] = []  # missed

        for key in pred_keys:
            if key not in ref_keys:
                false_positives.append(key)
            else:
                if self._values_match(ref_present[key], pred_present[key]):
                    true_positives.append(key)
                else:
                    false_positives.append(key)

        for key in ref_keys:
            if key not in pred_keys:
                false_negatives.append(key)

        tp = len(true_positives)
        fp = len(false_positives)
        fn = len(false_negatives)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        hallucination_rate = fp / len(pred_keys) if pred_keys else 0.0

        result = ExtractionEvalResult(
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            hallucination_rate=round(hallucination_rate, 4),
            hallucinated_fields=false_positives,
            missing_fields=false_negatives,
            num_reference_fields=len(ref_keys),
            num_predicted_fields=len(pred_keys),
        )

        logger.info(
            "Extraction Eval — P: %.4f, R: %.4f, F1: %.4f, Hallucination: %.4f",
            result.precision,
            result.recall,
            result.f1,
            result.hallucination_rate,
        )
        return result

    def _values_match(self, ref: object, pred: object) -> bool:
        """Return True if ref and pred represent the same value."""
        def normalize(v: object) -> object:
            if isinstance(v, str):
                return v if self.case_sensitive else v.lower().strip()
            if isinstance(v, list):
                items = [normalize(i) for i in v]
                return sorted(str(i) for i in items)
            return v

        return normalize(ref) == normalize(pred)
