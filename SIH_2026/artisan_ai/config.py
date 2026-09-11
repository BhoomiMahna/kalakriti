"""
artisan_ai.config
~~~~~~~~~~~~~~~~~

Central configuration for the Artisan AI pipeline.

All values can be overridden via environment variables or by passing
a ``Config`` instance to ``ArtisanProductPipeline``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# ── Supported Indian languages ────────────────────────────────────────────────
LANGUAGE_MAP: dict[str, str] = {
    "hi": "Hindi",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "or": "Odia",
    "en": "English",
    # Additional Whisper codes that may be returned
    "ur": "Urdu",
    "sa": "Sanskrit",
    "as": "Assamese",
    "sd": "Sindhi",
}

# ── Category → important fields for missing-field detection ──────────────────
CATEGORY_REQUIRED_FIELDS: dict[str, list[str]] = {
    "Clothing": [
        "material", "colors", "dimensions", "care_instructions",
        "craft_technique", "production_method",
    ],
    "Handicraft": [
        "material", "dimensions", "craft_technique", "craft_type",
        "region", "usage",
    ],
    "Jewelry": [
        "material", "colors", "dimensions", "weight",
        "craft_technique", "production_method",
    ],
    "Furniture": [
        "material", "dimensions", "weight", "colors", "usage",
    ],
    "Pottery": [
        "material", "dimensions", "weight", "usage", "craft_technique",
    ],
    "Textile": [
        "material", "colors", "dimensions", "care_instructions",
        "craft_technique", "production_method",
    ],
    "default": [
        "material", "colors", "dimensions", "usage", "craft_technique",
    ],
}


@dataclass
class Config:
    # ── LLM ──────────────────────────────────────────────────────────────────
    google_api_key: str = field(default_factory=lambda: _env("GOOGLE_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    gemini_model: str = "gemini-3.6-flash"
    openai_model: str = "gpt-4o-mini"
    llm_max_retries: int = field(
        default_factory=lambda: int(_env("LLM_MAX_RETRIES", "3"))
    )
    generation_temperature: float = field(
        default_factory=lambda: float(_env("GENERATION_TEMPERATURE", "0.3"))
    )

    # ── ASR ──────────────────────────────────────────────────────────────────
    asr_provider: str = field(
        default_factory=lambda: _env("ASR_PROVIDER", "whisper")
    )
    whisper_model_size: str = field(
        default_factory=lambda: _env("WHISPER_MODEL_SIZE", "large-v3")
    )

    # ── BHASHINI ─────────────────────────────────────────────────────────────
    bhashini_user_id: str = field(
        default_factory=lambda: _env("BHASHINI_USER_ID")
    )
    bhashini_api_key: str = field(
        default_factory=lambda: _env("BHASHINI_API_KEY")
    )
    bhashini_pipeline_id: str = field(
        default_factory=lambda: _env("BHASHINI_PIPELINE_ID", "64392f96dadc500b55c543cd")
    )

    # ── Sarvam AI ────────────────────────────────────────────────────────────
    sarvam_api_key: str = field(
        default_factory=lambda: _env("SARVAM_API_KEY")
    )

    # ── Translation ───────────────────────────────────────────────────────────
    translation_provider: Literal["indictrans2", "opus_mt"] = field(
        default_factory=lambda: _env("TRANSLATION_PROVIDER", "indictrans2")  # type: ignore[return-value]
    )
    indictrans2_repo_path: str = field(
        default_factory=lambda: _env("INDICTRANS2_REPO_PATH", "./IndicTrans2")
    )
    indictrans2_model: str = "ai4bharat/indictrans2-indic-en-dist-200M"

    # ── Device ────────────────────────────────────────────────────────────────
    device: Literal["auto", "cpu", "cuda", "mps"] = field(
        default_factory=lambda: _env("DEVICE", "auto")  # type: ignore[return-value]
    )

    # ── Validation ───────────────────────────────────────────────────────────
    forbidden_unsupported_phrases: list[str] = field(
        default_factory=lambda: [
            "eco-friendly", "sustainable", "organic", "certified",
            "premium quality", "luxury", "authentic", "traditional",
            "award-winning", "world-class", "best-in-class",
        ]
    )

    def resolve_device(self) -> str:
        """Return 'cuda', 'mps', or 'cpu' based on availability."""
        if self.device != "auto":
            return self.device
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def get_llm_provider(self) -> Literal["gemini", "openai"]:
        if self.google_api_key:
            return "gemini"
        if self.openai_api_key:
            return "openai"
        raise EnvironmentError(
            "No LLM API key found. Set GOOGLE_API_KEY (Gemini) or OPENAI_API_KEY "
            "in your .env file."
        )
