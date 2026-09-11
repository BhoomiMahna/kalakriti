"""
artisan_ai.evaluation.translation_eval
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Translation evaluation: BLEU and chrF scores.

Uses the ``sacrebleu`` library.  Install with::

    pip install sacrebleu

Example::

    from artisan_ai.evaluation.translation_eval import TranslationEvaluator

    evaluator = TranslationEvaluator()
    results = evaluator.evaluate(
        references=["This is a Phulkari dupatta made by hand."],
        hypotheses=["This is a hand-made Phulkari dupatta."],
    )
    print(results)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TranslationEvalResult:
    bleu: float
    chrf: float
    num_references: int


class TranslationEvaluator:
    """Evaluate translation quality using BLEU and chrF."""

    def evaluate(
        self,
        references: list[str],
        hypotheses: list[str],
    ) -> TranslationEvalResult:
        """Compute BLEU and chrF scores.

        Parameters
        ----------
        references:
            Ground-truth English translations.
        hypotheses:
            Model-generated English translations.

        Returns
        -------
        TranslationEvalResult
        """
        try:
            import sacrebleu  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "sacrebleu is required for translation evaluation. "
                "Install with: pip install sacrebleu"
            ) from exc

        if len(references) != len(hypotheses):
            raise ValueError(
                f"references ({len(references)}) and hypotheses "
                f"({len(hypotheses)}) must have the same length."
            )

        # sacrebleu expects a list of reference lists
        bleu = sacrebleu.corpus_bleu(hypotheses, [references])
        chrf = sacrebleu.corpus_chrf(hypotheses, [references])

        result = TranslationEvalResult(
            bleu=round(bleu.score, 2),
            chrf=round(chrf.score, 2),
            num_references=len(references),
        )
        logger.info(
            "Translation Eval — BLEU: %.2f, chrF: %.2f",
            result.bleu,
            result.chrf,
        )
        return result
