"""
tests/test_translation_multilang.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Multi-language integration test for IndicTransProvider.

Tests all 10 supported Indic languages through the fixed indictrans.py
implementation (IndicTransToolkit-based pipeline).

Run:
    cd /home/navya/SIH_2026/SIH_2026
    source .venv/bin/activate
    python tests/test_translation_multilang.py

The model downloads on first run (~800 MB). Subsequent runs use the
HuggingFace cache and start in ~30 seconds.
"""

from __future__ import annotations

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("multilang_test")

# ---------------------------------------------------------------------------
# Test sentences (one per language)
# ---------------------------------------------------------------------------
TEST_CASES: list[dict] = [
    {
        "lang_name": "Punjabi",
        "iso": "pa",
        "text": (
            "\u0a07\u0a39 \u0a2b\u0a41\u0a32\u0a15\u0a3e\u0a30\u0a40 \u0a26\u0a3e \u0a26\u0a41\u0a2a\u0a71\u0a1f\u0a3e \u0a39\u0a48\u0964"
            " \u0a07\u0a39 \u0a39\u0a71\u0a25 \u0a28\u0a3e\u0a32 \u0a2c\u0a23\u0a3e\u0a07\u0a06 \u0a17\u0a3f\u0a06 \u0a39\u0a48\u0964"
        ),
        "expected_keywords": ["Phulkari", "dupatta", "hand", "handmade"],
    },
    {
        "lang_name": "Hindi",
        "iso": "hi",
        "text": (
            "\u092f\u0939 \u090f\u0915 \u0939\u093e\u0925 \u0938\u0947 \u092c\u0928\u0940 \u0939\u0941\u0908"
            " \u0932\u0915\u095c\u0940 \u0915\u0940 \u092e\u0942\u0930\u094d\u0924\u093f \u0939\u0948\u0964"
        ),
        "expected_keywords": ["wooden", "statue", "hand"],
    },
    {
        "lang_name": "Tamil",
        "iso": "ta",
        "text": (
            "\u0b87\u0ba4\u0bc1 \u0b95\u0bc8\u0baf\u0bbe\u0bb2\u0bcd \u0b9a\u0bc6\u0baf\u0bcd\u0baf\u0baa\u0bcd\u0baa\u0b9f\u0bcd\u0b9f"
            " \u0baa\u0b9f\u0bcd\u0b9f\u0bc1 \u0baa\u0bbe\u0bb5\u0bbe\u0b9f\u0bc8\u0baf\u0bbe\u0b95\u0bc1\u0bae\u0bcd\u0964"
        ),
        "expected_keywords": ["handmade", "silk", "saree"],
    },
    {
        "lang_name": "Telugu",
        "iso": "te",
        "text": (
            "\u0c07\u0c26\u0c3f \u0c1a\u0c47\u0c24\u0c3f\u0c24\u0c4b \u0c24\u0c2f\u0c3e\u0c30\u0c41"
            " \u0c1a\u0c47\u0c38\u0c3f\u0c28 \u0c35\u0c38\u0c4d\u0c24\u0c4d\u0c30\u0c02\u0964"
        ),
        "expected_keywords": ["handmade", "cloth"],
    },
    {
        "lang_name": "Bengali",
        "iso": "bn",
        "text": (
            "\u098f\u099f\u09bf \u098f\u0995\u099f\u09bf \u09b9\u09be\u09a4\u09c7 \u09a4\u09c8\u09b0\u09bf"
            " \u09ae\u09be\u099f\u09bf\u09b0 \u09aa\u09be\u09a4\u09cd\u09b0\u0964"
        ),
        "expected_keywords": ["handmade", "clay", "pot"],
    },
    {
        "lang_name": "Marathi",
        "iso": "mr",
        "text": (
            "\u0939\u0940 \u0939\u093e\u0924\u093e\u0928\u0947 \u0935\u093f\u0923\u0932\u0947\u0932\u0940"
            " \u0936\u093e\u0932 \u0906\u0939\u0947\u0964"
        ),
        "expected_keywords": ["handwoven", "shawl"],
    },
    {
        "lang_name": "Gujarati",
        "iso": "gu",
        "text": (
            "\u0a86 \u0a39\u0a3e\u0a25\u0a2c\u0a28\u0a3e\u0a35\u0a1f\u0a28\u0a41\u0a02"
            " \u0a2d\u0a30\u0a24\u0a15\u0a3e\u0a2e \u0a15\u0a30\u0a47\u0a32\u0a3e\u0a02"
            " \u0a39\u0a38\u0a4d\u0a24\u0a15\u0a32\u0a3e\u0a28\u0a41\u0a02 \u0a15\u0a3e\u0a2e \u0a2a\u0a23 \u0a15\u0a30\u0a30\u0a47 \u0a15\u0a38\u0a4d\u0a24\u0a41\u0a30\u0a40 \u0a35\u0a38\u0a4d\u0a24\u0a4d\u0a30 \u0a1b\u0a47\u0964"
        ),
        "expected_keywords": ["embroidery", "handmade"],
    },
    {
        "lang_name": "Kannada",
        "iso": "kn",
        "text": (
            "\u0c87\u0ca6\u0cc1 \u0c95\u0cc8\u0caf\u0cbf\u0c82\u0ca6 \u0ca8\u0cc7\u0ca6"
            " \u0cae\u0cbe\u0ca1\u0cbf\u0ca6 \u0c9a\u0cc0\u0cb0\u0cc6\u0caf\u0cbe\u0c97\u0cbf\u0ca6\u0cc6\u0964"
        ),
        "expected_keywords": ["handwoven", "saree"],
    },
    {
        "lang_name": "Malayalam",
        "iso": "ml",
        "text": (
            "\u0d07\u0d24\u0d4d \u0d15\u0d48\u0d15\u0d4a\u0d23\u0d4d\u0d1f\u0d4d"
            " \u0d09\u0d23\u0d4d\u0d1f\u0d3e\u0d15\u0d4d\u0d15\u0d3f\u0d2f"
            " \u0d2e\u0d30\u0d2a\u0d4d\u0d2a\u0d23\u0d3f\u0d2f\u0d3e\u0d23\u0d4d\u0964"
        ),
        "expected_keywords": ["handmade", "wooden"],
    },
    {
        "lang_name": "Odia",
        "iso": "or",
        "text": (
            "\u0b8f\u0bb9\u0bbe \u0b8f\u0b95\u0b9f\u0bbf \u0b39\u0b38\u0bcd\u0ba4"
            " \u0ba4\u0bbe\u0ba4\u0bbf \u0b95\u0bbe\u0baa\u0b9c \u0b85\u0b9f\u0bbe\u0bb3\u0bc1\u0964"
        ),
        "expected_keywords": ["handloom", "cloth"],
    },
]


def run_tests() -> None:
    from artisan_ai.translation.indictrans import IndicTransProvider

    print("\n" + "=" * 70)
    print("IndicTrans2 Multi-Language Translation Test")
    print("=" * 70)

    provider = IndicTransProvider()  # Model loads on first translate() call

    passed = 0
    failed = 0
    errors = 0

    for case in TEST_CASES:
        lang = case["lang_name"]
        iso = case["iso"]
        text = case["text"]

        print(f"\n[{lang} / {iso}]")
        print(f"  Input : {text}")

        try:
            t0 = time.perf_counter()
            result = provider.translate(text, source_language=iso)
            elapsed = time.perf_counter() - t0

            print(f"  Output: {result.translated_text}")
            print(f"  Time  : {elapsed:.1f}s")
            print(f"  Model : {result.model_name}")

            if result.translated_text.strip():
                print(f"  Status: PASS")
                passed += 1
            else:
                print(f"  Status: FAIL (empty output)")
                failed += 1

        except Exception as exc:
            print(f"  Status: ERROR — {exc}")
            errors += 1

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed / {failed} failed / {errors} errors")
    print("=" * 70 + "\n")

    if failed + errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
