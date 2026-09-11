"""
artisan_ai.translation.base
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Abstract base class for all translation providers.

Any translation backend (IndicTrans2, Helsinki opus-mt, etc.) must
implement this interface so the pipeline stays model-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranslationResult:
    """Output of any translation provider.

    Attributes
    ----------
    translated_text:
        The translated text.
    source_language:
        ISO 639-1 code of the source language.
    target_language:
        ISO 639-1 code of the target language.
    model_name:
        Translation model identifier.
    """

    translated_text: str
    source_language: str
    target_language: str
    model_name: str = ""


class TranslationProvider(ABC):
    """Abstract interface for translation backends."""

    @abstractmethod
    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str = "en",
    ) -> TranslationResult:
        """Translate *text* from *source_language* to *target_language*.

        Parameters
        ----------
        text:
            The text to translate (original language).
        source_language:
            ISO 639-1 code of the source language (e.g. ``"pa"``).
        target_language:
            ISO 639-1 code of the target language.  Defaults to ``"en"``.

        Returns
        -------
        TranslationResult
        """
        ...
