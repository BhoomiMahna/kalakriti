"""
artisan_ai
~~~~~~~~~~

Multilingual Voice-to-Product-Description AI Pipeline for Indian Artisans.

Usage::

    from artisan_ai import ArtisanProductPipeline

    pipeline = ArtisanProductPipeline()
    result = pipeline.process("artisan_audio.wav")
"""

from artisan_ai.pipeline import ArtisanProductPipeline

__all__ = ["ArtisanProductPipeline"]
__version__ = "0.1.0"
