"""
example_usage.py
~~~~~~~~~~~~~~~~~

Runnable demonstration of the ArtisanProductPipeline.

This script shows three usage modes:

  1. Full pipeline from audio file
  2. Pipeline from pre-existing transcript (no audio file needed)
  3. Follow-up question update

Run::

    python example_usage.py

Environment variables required::

    GOOGLE_API_KEY=your_gemini_api_key

Optional (only if running full audio mode)::

    WHISPER_MODEL_SIZE=medium   (or large-v3)
    TRANSLATION_PROVIDER=indictrans2
"""

from __future__ import annotations

import json
import logging
import os
import sys

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("example")


def demo_from_transcript() -> dict:
    """
    Demo mode: bypass ASR and translation, inject a known transcript.

    This is useful for testing extraction, generation, and validation
    without downloading any ASR or translation models.
    """
    from unittest.mock import MagicMock

    from artisan_ai import ArtisanProductPipeline
    from artisan_ai.asr.base import TranscriptResult
    from artisan_ai.audio.preprocessing import PreprocessedAudio
    from artisan_ai.config import Config
    from artisan_ai.translation.base import TranslationResult

    print("\n" + "=" * 60)
    print("DEMO MODE: Transcript injection (no ASR/translation models)")
    print("=" * 60)

    config = Config()
    if not config.google_api_key:
        print("\n[ERROR] GOOGLE_API_KEY not set in environment or .env file.")
        print("Copy .env.example → .env and add your key.")
        sys.exit(1)

    # ── Mock ASR: Punjabi Phulkari dupatta ────────────────────────────────────
    mock_asr = MagicMock()
    mock_asr.transcribe.return_value = TranscriptResult(
        transcript=(
            "ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ। ਇਹ ਅਸੀਂ ਹੱਥ ਨਾਲ ਬਣਾਇਆ ਹੈ। "
            "ਇਸ ਵਿੱਚ ਸੂਤੀ ਕੱਪੜਾ ਵਰਤਿਆ ਹੈ ਅਤੇ ਇਸ ਉੱਤੇ ਲਾਲ ਤੇ ਪੀਲੇ "
            "ਰੰਗ ਦੀ ਕਢਾਈ ਕੀਤੀ ਹੈ।"
        ),
        language_code="pa",
        language_name="Punjabi",
        confidence=0.97,
        model_name="whisper-large-v3 [mocked]",
    )

    # ── Mock Translator ────────────────────────────────────────────────────────
    mock_translator = MagicMock()
    mock_translator.translate.return_value = TranslationResult(
        translated_text=(
            "This is a Phulkari dupatta. We made it by hand. "
            "It uses cotton fabric and has red and yellow embroidery."
        ),
        source_language="pa",
        target_language="en",
        model_name="IndicTrans2 [mocked]",
    )

    # ── Mock Preprocessor ─────────────────────────────────────────────────────
    mock_preprocessor = MagicMock()
    mock_preprocessor.process.return_value = PreprocessedAudio(
        path="[mocked audio path]",
        sample_rate=16000,
        channels=1,
        duration_seconds=8.0,
        original_path="[mocked]",
    )

    pipeline = ArtisanProductPipeline(
        config=config,
        asr_provider=mock_asr,
        translation_provider=mock_translator,
        preprocessor=mock_preprocessor,
    )

    result = pipeline.process("artisan_audio.wav [mocked]")
    return result


def demo_from_audio(audio_path: str) -> dict:
    """
    Full pipeline demo from a real audio file.

    Requires:
      - ffmpeg installed on PATH
      - GOOGLE_API_KEY in .env
      - WHISPER_MODEL_SIZE set (default: large-v3)
      - TRANSLATION_PROVIDER=indictrans2 or opus_mt
    """
    from artisan_ai import ArtisanProductPipeline

    print("\n" + "=" * 60)
    print(f"FULL PIPELINE MODE: {audio_path}")
    print("=" * 60)

    pipeline = ArtisanProductPipeline()
    result = pipeline.process(audio_path)
    return result


def print_result(result: dict) -> None:
    print("\n" + "=" * 60)
    print("PIPELINE OUTPUT")
    print("=" * 60)

    lang = result["language"]
    print(f"\n📢 Language: {lang['name']} ({lang['code']})")

    print(f"\n📝 Original Transcript:\n{result['transcription']['original']}")
    print(f"\n🌐 English Translation:\n{result['translation']['english']}")

    print("\n📦 Product Facts:")
    facts = result["product_facts"]
    for field, value in facts.items():
        if value is not None:
            print(f"   {field}: {value}")

    missing = result["missing_fields"]
    if missing:
        print(f"\n⚠️  Missing Fields: {', '.join(missing)}")

    questions = result["follow_up_questions"]
    if questions:
        print(f"\n❓ Follow-Up Questions ({len(questions)}):")
        for q in questions:
            print(f"   [{q['field']}] EN: {q['question_en']}")
            if q.get("question_local"):
                print(f"            Local: {q['question_local']}")

    listing = result["listing"]
    print(f"\n🛒 Generated Listing:")
    print(f"   Title: {listing['title']}")
    print(f"   Short: {listing['short_description']}")
    print(f"\n   Description:\n{listing['description']}")
    print(f"\n   Highlights:")
    for h in listing["highlights"]:
        print(f"     • {h}")
    print(f"\n   Keywords: {', '.join(listing['keywords'])}")

    validation = result["validation"]
    status = "✅ VALID" if validation["valid"] else "❌ INVALID"
    print(f"\n{status} — Factual Validation")
    if not validation["valid"]:
        print("   Unsupported claims:")
        for claim in validation["unsupported_claims"]:
            print(f"     ✗ {claim}")

    print("\n" + "=" * 60)
    print("Full JSON output:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # ── Check for audio file argument ────────────────────────────────────────
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        if not os.path.exists(audio_file):
            print(f"[ERROR] Audio file not found: {audio_file}")
            sys.exit(1)
        result = demo_from_audio(audio_file)
    else:
        print(
            "[INFO] No audio file provided. Running in transcript-injection demo mode.\n"
            "[INFO] To run with real audio: python example_usage.py <audio_file.wav>"
        )
        result = demo_from_transcript()

    print_result(result)
