"""
Central application settings.

All values are read from environment variables / a .env file so that
secrets (marketplace credentials, JWT keys, LLM keys) never live in code.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository layout:
#   D:\sih2026\
#     ├── app\backend\        <- this file lives in app/backend/core/
#     ├── SIH_2026\artisan_ai <- the provided AI pipeline package
#     └── pricing_model.pkl   <- the provided pricing model
BACKEND_DIR = Path(__file__).resolve().parents[1]        # app/backend
APP_DIR = BACKEND_DIR.parent                              # app
REPO_ROOT = APP_DIR.parent                                # D:\sih2026
ARTISAN_AI_ROOT = REPO_ROOT / "SIH_2026"                  # holds artisan_ai + IndicTrans2


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "Artisan Platform API"
    environment: str = "development"
    debug: bool = True
    api_base_url: str = "http://localhost:8000"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'artisan.db').as_posix()}"

    # ── Auth ─────────────────────────────────────────────────────────────────
    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60 * 24 * 7          # 7 days
    otp_expiry_seconds: int = 300                  # 5 minutes
    otp_dev_mode: bool = True                       # return OTP in response (dev only)

    # ── Storage ──────────────────────────────────────────────────────────────
    storage_dir: str = str(BACKEND_DIR / "storage")

    # ── AI pipeline ──────────────────────────────────────────────────────────
    # When these are absent, the AI service falls back to a deterministic
    # heuristic pipeline so the app still runs end-to-end without a GPU.
    enable_ai_pipeline: bool = False               # set True once artisan_ai deps installed
    artisan_ai_root: str = str(ARTISAN_AI_ROOT)
    google_api_key: str = ""

    # ── Sarvam AI speech-to-text (real, no GPU needed) ───────────────────────
    # When set, artisan voice recordings are transcribed AND translated to
    # English via Sarvam's speech-to-text-translate API.
    sarvam_api_key: str = ""
    sarvam_stt_model: str = "saaras:v2.5"

    # ── Pricing model ────────────────────────────────────────────────────────
    pricing_model_path: str = str(REPO_ROOT / "pricing_model.pkl")
    pricing_reference_csv: str = str(REPO_ROOT / "reference_listings.csv")
    pricing_reference_embeddings: str = str(REPO_ROOT / "reference_embeddings.npy")

    # ── AI Product Photoshoot (generative images) ────────────────────────────
    # Provider for the generative product photoshoot (hero/lifestyle/detail).
    #   ""  or "demo" -> demo compositor (no GPU/keys; clearly labelled)
    #   "flux_url"    -> POST reference image + prompt to a hosted FLUX service
    #   "gemini"      -> Gemini image generation (needs GOOGLE_API_KEY)
    #   "openai"      -> OpenAI image edit (needs OPENAI_API_KEY)
    image_provider: str = ""
    image_enhancer_url: str = ""            # FLUX service endpoint (provider=flux_url)
    openai_api_key: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image-preview"
    # Background-removal model for the local isolation pipeline (rembg).
    #   u2netp = fast/light (~4MB), u2net = higher quality (~170MB).
    image_rembg_model: str = "u2netp"
    # Reject a "generated" shot if it is this perceptually close to the input
    # (phash Hamming distance). Guards against silently returning the original.
    image_min_phash_distance: int = 8

    # Deterministic photoshoot demo: when a KNOWN before/source image is
    # uploaded, skip generation and return the curated professional AFTER assets
    # from `demo_products_dir` (mapped by SHA-256). Real Gemini/isolation path is
    # used for every other (non-matching) image. On for hackathon reliability.
    image_demo_mode: bool = True
    demo_products_dir: str = str(REPO_ROOT / "before_after_products")

    # ── Demo mode ────────────────────────────────────────────────────────────
    # Master switch for the judge-demo experience: simulated marketplace
    # publishing + internal demo listing pages. Real credentials always take
    # precedence over simulation, per channel.
    demo_mode: bool = True

    # ── Amazon SP-API ────────────────────────────────────────────────────────
    amazon_enabled: bool = False
    amazon_lwa_client_id: str = ""
    amazon_lwa_client_secret: str = ""
    amazon_refresh_token: str = ""
    amazon_marketplace_id: str = "A21TJRUUN4KGV"    # amazon.in
    amazon_seller_id: str = ""
    amazon_region: str = "eu"                        # na | eu | fe  (India lives in eu)
    amazon_sandbox: bool = True

    # ── Instagram automation (artisans_ai.instagram package) ─────────────────
    # Platform-level, single central brand account. Demo mode simulates
    # publishing (no Meta creds needed) — clearly labelled, never claimed real.
    instagram_enabled: bool = True
    instagram_demo_mode: bool = True
    instagram_account_handle: str = "@kalakriti.craft"
    instagram_post_threshold: float = 0.55   # lower than package default (0.85) so the demo reliably posts
    gemini_api_key: str = ""                  # falls back to google_api_key, then offline generator
    # Meta Graph API credentials (real mode only)
    ig_access_token: str = ""
    ig_business_account_id: str = ""
    instagram_feedback_path: str = ""         # defaults to storage/instagram_feedback.jsonl
    repo_root: str = str(REPO_ROOT)           # so `artisans_ai` package is importable

    # ── ONDC ─────────────────────────────────────────────────────────────────
    ondc_enabled: bool = False
    ondc_base_url: str = "https://staging.registry.ondc.org"
    ondc_subscriber_id: str = ""
    ondc_signing_private_key: str = ""
    ondc_unique_key_id: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
