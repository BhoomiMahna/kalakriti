"""
test_sarvam_asr.py
~~~~~~~~~~~~~~~~~~~

Standalone test for the Sarvam AI ASR provider.

Usage:
    python test_sarvam_asr.py [audio_file.wav] [language_code]

Examples:
    python test_sarvam_asr.py artisan_audio.wav pa
    python test_sarvam_asr.py artisan_audio.wav hi
    python test_sarvam_asr.py artisan_audio.wav auto

Requires: SARVAM_API_KEY in .env
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


def main() -> None:
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "artisan_audio.wav"
    source_lang = sys.argv[2] if len(sys.argv) > 2 else "unknown"

    if not os.path.isfile(audio_path):
        print(f"[ERROR] Audio file not found: {audio_path}")
        print("Usage: python test_sarvam_asr.py <audio.wav> [language_code]")
        sys.exit(1)

    from dotenv import load_dotenv
    load_dotenv()

    from artisan_ai.config import Config
    config = Config()

    if not config.sarvam_api_key:
        print()
        print("=" * 60)
        print("SARVAM API KEY NOT FOUND")
        print("=" * 60)
        print("Set SARVAM_API_KEY in your .env file.")
        print("Get your key at https://console.sarvam.ai")
        sys.exit(1)

    print()
    print("=" * 60)
    print("Sarvam AI ASR — Standalone Test")
    print("=" * 60)
    print(f"  Audio    : {audio_path}")
    print(f"  Language : {source_lang}")
    print(f"  Size     : {os.path.getsize(audio_path):,} bytes")
    print()

    from artisan_ai.asr.sarvam_asr import SarvamASR

    asr = SarvamASR(
        config=config,
        source_language=source_lang if source_lang != "auto" else None,
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
        print("\u2705  Sarvam AI ASR test passed.")

    except EnvironmentError as exc:
        print(f"\n[CONFIG ERROR] {exc}")
        sys.exit(1)
    except RuntimeError as exc:
        print(f"\n[API ERROR] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
