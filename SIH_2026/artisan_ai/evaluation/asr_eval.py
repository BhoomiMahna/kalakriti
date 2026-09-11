"""
artisan_ai.evaluation.asr_eval
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ASR evaluation: Word Error Rate (WER) and Character Error Rate (CER).

Uses the ``jiwer`` library.  Install with::

    pip install jiwer

Example::

    from artisan_ai.evaluation.asr_eval import ASREvaluator

    evaluator = ASREvaluator()
    results = evaluator.evaluate(
        references=["ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ"],
        hypotheses=["ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ"],
    )
    print(results)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ASREvalResult:
    wer: float
    cer: float
    num_references: int


class ASREvaluator:
    """Evaluate ASR output using WER and CER."""

    def evaluate(
        self,
        references: list[str],
        hypotheses: list[str],
    ) -> ASREvalResult:
        """Compute WER and CER between *references* and *hypotheses*.

        Parameters
        ----------
        references:
            Ground-truth transcripts.
        hypotheses:
            ASR-generated transcripts.

        Returns
        -------
        ASREvalResult
        """
        try:
            import jiwer  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "jiwer is required for ASR evaluation. "
                "Install with: pip install jiwer"
            ) from exc

        if len(references) != len(hypotheses):
            raise ValueError(
                f"references ({len(references)}) and hypotheses "
                f"({len(hypotheses)}) must have the same length."
            )

        wer = jiwer.wer(references, hypotheses)
        cer = jiwer.cer(references, hypotheses)

        result = ASREvalResult(
            wer=round(wer, 4),
            cer=round(cer, 4),
            num_references=len(references),
        )
        logger.info("ASR Eval — WER: %.4f, CER: %.4f", result.wer, result.cer)
        return result

    def evaluate_single(self, reference: str, hypothesis: str) -> ASREvalResult:
        return self.evaluate([reference], [hypothesis])
