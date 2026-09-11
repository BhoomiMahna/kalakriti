"""
artisan_ai.asr.base
~~~~~~~~~~~~~~~~~~~~

Abstract base class for all ASR providers.

Any ASR model (Whisper, IndicConformer, etc.) must implement this interface
so the pipeline remains model-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptResult:
    """The output of any ASR provider.

    Attributes
    ----------
    transcript:
        The raw transcript in the *original* spoken language.
        Do NOT return an English translation here.
    language_code:
        ISO 639-1 language code detected by the ASR model
        (e.g. ``"pa"`` for Punjabi, ``"hi"`` for Hindi).
    language_name:
        Human-readable language name (e.g. ``"Punjabi"``).
    confidence:
        ASR model's reported confidence in the detected language.
        Set to ``None`` if the model does not provide this value.
    model_name:
        Name / version of the ASR model used.
    """

    transcript: str
    language_code: str
    language_name: str
    confidence: float | None = None
    model_name: str = ""


class ASRProvider(ABC):
    """Abstract interface for ASR (Automatic Speech Recognition) backends."""

    @abstractmethod
    def transcribe(self, audio_path: str) -> TranscriptResult:
        """Transcribe speech from *audio_path*.

        Parameters
        ----------
        audio_path:
            Path to a preprocessed 16 kHz mono WAV file.

        Returns
        -------
        TranscriptResult
            The original-language transcript and detected language metadata.
        """
        ...
