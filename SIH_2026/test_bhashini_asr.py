"""
test_bhashini_asr.py
~~~~~~~~~~~~~~~~~~~~~

Standalone test for the BHASHINI ASR provider.

Tests ONLY the speech-to-text component — does NOT run IndicTrans2,
Gemini, or the rest of the pipeline.

Usage:
    cd ~/SIH_2026/SIH_2026
    source ~/SIH_2026/.venv/bin/activate
    python test_bhashini_asr.py [audio_file.wav] [language_code]

Examples:
    python test_bhashini_asr.py artisan_audio.wav pa
    python test_bhashini_asr.py artisan_audio.wav hi

Requires:
    BHASHINI_USER_ID and BHASHINI_API_KEY in .env
"""

from __future__ import annotations

import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bhashini_test")


def main() -> None:
    # Parse args
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "artisan_audio.wav"
    source_lang = sys.argv[2] if len(sys.argv) > 2 else "pa"

    if not os.path.isfile(audio_path):
        print(f"[ERROR] Audio file not found: {audio_path}")
        print("Usage: python test_bhashini_asr.py <audio_file.wav> [language_code]")
        sys.exit(1)

    # Load config
    from dotenv import load_dotenv
    load_dotenv()

    from artisan_ai.config import Config
    config = Config()

    if not config.bhashini_user_id or not config.bhashini_api_key:
        print()
        print("=" * 60)
        print("BHASHINI CREDENTIALS NOT FOUND")
        print("=" * 60)
        print()
        print("Set the following in your .env file:")
        print("  BHASHINI_USER_ID=your_user_id")
        print("  BHASHINI_API_KEY=your_api_key")
        print()
        print("Register at https://bhashini.gov.in to obtain credentials.")
        print()
        sys.exit(1)

    print()
    print("=" * 60)
    print("BHASHINI ASR — Standalone Test")
    print("=" * 60)
    print(f"  Audio file : {audio_path}")
    print(f"  Language   : {source_lang}")
    print(f"  File size  : {os.path.getsize(audio_path):,} bytes")
    print()

    from artisan_ai.asr.bhashini_asr import BhashiniASR

    asr = BhashiniASR(
        config=config,
        source_language=source_lang,
    )

    try:
        t0 = time.perf_counter()
        result = asr.transcribe(audio_path)
        elapsed = time.perf_counter() - t0

        print("RESULT:")
        print(f"  Transcript : {result.transcript}")
        print(f"  Language   : {result.language_name} ({result.language_code})")
        print(f"  Model      : {result.model_name}")
        print(f"  Time       : {elapsed:.1f}s")
        print()
        print("\u2705  BHASHINI ASR test passed.")

    except EnvironmentError as exc:
        print(f"\n[CONFIG ERROR] {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"\n[API ERROR] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] {type(exc).__name__}: {exc}")
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
