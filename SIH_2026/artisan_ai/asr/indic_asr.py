"""
artisan_ai.asr.indic_asr
~~~~~~~~~~~~~~~~~~~~~~~~~

Stub for AI4Bharat IndicConformer ASR integration.

AI4Bharat's IndicConformer family provides state-of-the-art ASR for
Indian languages.  This stub implements the ``ASRProvider`` interface
so it can be swapped in without pipeline changes once the model
integration is complete.

Setup
-----
1. Clone the AI4Bharat ASR repo::

       git clone https://github.com/AI4Bharat/IndicConformer

2. Follow the installation instructions in the repo.

3. Set the environment variable::

       INDIC_CONFORMER_MODEL_PATH=/path/to/checkpoint

Reference
---------
https://github.com/AI4Bharat/IndicConformer
"""

from __future__ import annotations

import logging
import os
from typing import Any

from artisan_ai.asr.base import ASRProvider, TranscriptResult
from artisan_ai.config import LANGUAGE_MAP

logger = logging.getLogger(__name__)


class IndicConformerASR(ASRProvider):
    """ASR provider backed by AI4Bharat IndicConformer.

    Parameters
    ----------
    model_path:
        Path to the IndicConformer model checkpoint directory.
        Defaults to the ``INDIC_CONFORMER_MODEL_PATH`` environment variable.
    language:
        ISO 639-1 code of the expected language.  IndicConformer models are
        often language-specific, so this should be set explicitly.
    device:
        ``"cpu"`` or ``"cuda"``.
    """

    def __init__(
        self,
        model_path: str | None = None,
        language: str | None = None,
        device: str = "cpu",
    ) -> None:
        self.model_path = model_path or os.environ.get(
            "INDIC_CONFORMER_MODEL_PATH", ""
        )
        self.language = language
        self.device = device
        self._model: Any = None

    def _load_model(self) -> None:
        if self._model is not None:
            return

        if not self.model_path:
            raise EnvironmentError(
                "IndicConformerASR requires a model path. "
                "Set INDIC_CONFORMER_MODEL_PATH or pass model_path=..."
            )

        # ── Integration point ─────────────────────────────────────────────────
        # Replace the block below with actual IndicConformer loading code
        # once the dependency is installed.
        #
        # Example (subject to IndicConformer's actual API):
        #
        #   from nemo.collections.asr.models import EncDecCTCModelBPE
        #   self._model = EncDecCTCModelBPE.restore_from(self.model_path)
        #   self._model = self._model.to(self.device)
        #
        raise NotImplementedError(
            "IndicConformer integration is not yet complete. "
            "See artisan_ai/asr/indic_asr.py for instructions."
        )

    def transcribe(self, audio_path: str) -> TranscriptResult:
        """Transcribe using IndicConformer (once integrated).

        Parameters
        ----------
        audio_path:
            Path to a preprocessed 16 kHz mono WAV file.
        """
        self._load_model()

        # ── Integration point ─────────────────────────────────────────────────
        # Replace the block below with actual IndicConformer inference.
        #
        # Example (subject to IndicConformer's actual API):
        #
        #   transcriptions = self._model.transcribe([audio_path])
        #   text = transcriptions[0]
        #   lang_code = self.language or "und"
        #   lang_name = LANGUAGE_MAP.get(lang_code, lang_code.title())
        #   return TranscriptResult(
        #       transcript=text,
        #       language_code=lang_code,
        #       language_name=lang_name,
        #       model_name="ai4bharat/indic-conformer",
        #   )
        #
        raise NotImplementedError(
            "IndicConformer transcription is not yet implemented. "
            "See artisan_ai/asr/indic_asr.py for integration instructions."
        )
