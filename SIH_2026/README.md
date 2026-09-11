# Artisan AI — Multilingual Voice-to-Product-Description Pipeline

A modular Python AI/ML pipeline that converts Indian artisan audio recordings into professional English e-commerce product descriptions.

---

## Architecture

```
AUDIO INPUT (.wav / .mp3 / .m4a / .webm)
     ↓
AudioPreprocessor   → format conversion, 16kHz mono, VAD trim
     ↓
WhisperASR          → original language transcript + language detection
     ↓
LanguageDetector    → confirmed language code + name
     ↓
IndicTrans2         → English translation (preserving original transcript)
     ↓
ProductExtractor    → Structured ProductFacts JSON (LLM, JSON mode)
     ↓
FollowUpGenerator   → Missing fields + artisan questions (in local language)
     ↓
DescriptionGenerator→ Professional listing from facts only
     ↓
FactualValidator    → Rule-based + LLM claim verification
     ↓
FINAL OUTPUT JSON
```

---

## Supported Languages

| Language | Code |
|----------|------|
| Hindi | `hi` |
| Punjabi | `pa` |
| Tamil | `ta` |
| Telugu | `te` |
| Bengali | `bn` |
| Marathi | `mr` |
| Gujarati | `gu` |
| Kannada | `kn` |
| Malayalam | `ml` |
| Odia | `or` |
| English | `en` |

---

## Project Structure

```
artisan_ai/
├── __init__.py           ← Public API: ArtisanProductPipeline
├── pipeline.py           ← Main orchestrator
├── config.py             ← Config (env vars, language maps, category rules)
│
├── audio/
│   └── preprocessing.py  ← Format conversion, resample, mono, VAD
│
├── asr/
│   ├── base.py           ← ASRProvider abstract class
│   ├── whisper_asr.py    ← Whisper (openai-whisper or transformers)
│   └── indic_asr.py      ← IndicConformer stub (ready for integration)
│
├── language/
│   └── detection.py      ← Language detection (ASR → langdetect fallback)
│
├── translation/
│   ├── base.py           ← TranslationProvider abstract class
│   ├── indictrans.py     ← IndicTrans2 (primary)
│   └── opus_mt.py        ← Helsinki opus-mt (fallback, pip-only)
│
├── extraction/
│   ├── product_schema.py ← Pydantic schemas (ProductFacts, EvidencedField, ...)
│   └── extractor.py      ← LLM-based fact extractor (JSON mode, retry logic)
│
├── followup/
│   └── question_generator.py ← Missing field detection + question generation
│
├── generation/
│   └── description_generator.py ← LLM listing generator (facts-only)
│
├── validation/
│   └── factual_validator.py  ← Rule-based + LLM factual validation
│
└── evaluation/
    ├── asr_eval.py       ← WER, CER (jiwer)
    ├── translation_eval.py ← BLEU, chrF (sacrebleu)
    ├── extraction_eval.py  ← Precision, Recall, F1, hallucination rate
    └── description_eval.py ← Unsupported claim rate, fact coverage, ROUGE-L

tests/
├── test_audio.py
├── test_asr.py
├── test_extraction.py
├── test_validation.py
├── test_pipeline.py
└── fixtures/
    ├── punjabi_sample_transcript.json
    └── expected_output.json
```

---

## Setup

### 1. Prerequisites

- Python 3.10+
- `ffmpeg` installed on your system PATH:
  - Windows: [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
  - Linux: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API keys

```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### 4. IndicTrans2 setup (primary translation model)

```bash
git clone https://github.com/AI4Bharat/IndicTrans2.git
pip install -e ./IndicTrans2/huggingface_interface
```

Set in `.env`:
```
INDICTRANS2_REPO_PATH=./IndicTrans2
```

> **Alternative**: If you skip IndicTrans2, set `TRANSLATION_PROVIDER=opus_mt` in `.env`. The opus-mt models are fully pip-installable with no extra setup.

---

## Quick Start

### Option A — Demo mode (no audio file, no ASR/translation models)

```bash
python example_usage.py
```

This injects a known Punjabi transcript and runs only extraction, generation, and validation (requires `GOOGLE_API_KEY`).

### Option B — Full pipeline from audio

```bash
python example_usage.py artisan_audio.wav
```

### Option C — Python API

```python
from artisan_ai import ArtisanProductPipeline

pipeline = ArtisanProductPipeline()
result = pipeline.process("artisan_audio.wav")

print(result["listing"]["title"])
print(result["validation"]["valid"])
```

---

## Output Format

```json
{
  "language": {
    "code": "pa",
    "name": "Punjabi",
    "confidence": 0.97
  },
  "transcription": {
    "original": "ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ..."
  },
  "translation": {
    "english": "This is a Phulkari dupatta..."
  },
  "product_facts": {
    "product_name": "Phulkari Dupatta",
    "category": "Clothing",
    "material": ["Cotton"],
    "colors": ["Red", "Yellow"],
    "craft_technique": "Phulkari embroidery",
    "region": null
  },
  "product_facts_with_evidence": {
    "product_name": {
      "value": "Phulkari Dupatta",
      "status": "supported",
      "evidence": "This is a Phulkari dupatta"
    }
  },
  "missing_fields": ["dimensions", "care_instructions"],
  "follow_up_questions": [
    {
      "field": "dimensions",
      "question_en": "What are the approximate dimensions of the dupatta?",
      "question_local": "ਇਸ ਦੁਪੱਟੇ ਦਾ ਲਗਭਗ ਆਕਾਰ ਕੀ ਹੈ?"
    }
  ],
  "listing": {
    "title": "Handcrafted Phulkari Cotton Dupatta",
    "short_description": "...",
    "description": "...",
    "highlights": ["Handmade Phulkari embroidery"],
    "keywords": ["phulkari", "dupatta", "cotton"]
  },
  "validation": {
    "valid": true,
    "unsupported_claims": []
  }
}
```

---

## Follow-up Audio Integration

When an artisan provides additional information, merge it with existing facts:

```python
# First recording
result = pipeline.process("initial_audio.wav")

# Artisan provides follow-up (e.g., answered dimension question)
updated = pipeline.update_product_facts(
    existing_facts=result["product_facts"],
    follow_up_audio="followup_audio.wav",
)
```

Existing `"supported"` fields are **never overwritten** by the follow-up.

---

## Replacing Models

Every component implements an abstract interface. To swap in a different model:

```python
from artisan_ai import ArtisanProductPipeline
from artisan_ai.asr.indic_asr import IndicConformerASR
from artisan_ai.translation.opus_mt import OpusMTProvider

pipeline = ArtisanProductPipeline(
    asr_provider=IndicConformerASR(model_path="...", language="hi"),
    translation_provider=OpusMTProvider(),
)
result = pipeline.process("audio.wav")
```

---

## Evaluation

```python
from artisan_ai.evaluation.asr_eval import ASREvaluator
from artisan_ai.evaluation.translation_eval import TranslationEvaluator
from artisan_ai.evaluation.extraction_eval import ExtractionEvaluator
from artisan_ai.evaluation.description_eval import DescriptionEvaluator

# ASR
asr_eval = ASREvaluator()
print(asr_eval.evaluate(references=["ground truth"], hypotheses=["asr output"]))

# Translation
trans_eval = TranslationEvaluator()
print(trans_eval.evaluate(references=["reference EN"], hypotheses=["translated EN"]))

# Extraction (no hallucinations)
ext_eval = ExtractionEvaluator()
print(ext_eval.evaluate(reference_facts=ground_truth, predicted_facts=extracted))

# Description
desc_eval = DescriptionEvaluator()
print(desc_eval.evaluate(facts=facts, listing=listing, unsupported_claims=[]))
```

---

## Running Tests

```bash
# All tests (mocked — no models required, no API key required)
pytest tests/ -v

# Specific modules
pytest tests/test_extraction.py -v
pytest tests/test_validation.py -v
pytest tests/test_pipeline.py -v
```

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | — | Gemini API key (required) |
| `OPENAI_API_KEY` | — | OpenAI fallback key (optional) |
| `WHISPER_MODEL_SIZE` | `large-v3` | ASR model size |
| `TRANSLATION_PROVIDER` | `indictrans2` | `indictrans2` or `opus_mt` |
| `INDICTRANS2_REPO_PATH` | `./IndicTrans2` | Path to IndicTrans2 clone |
| `DEVICE` | `auto` | `auto`, `cpu`, `cuda`, `mps` |
| `LLM_MAX_RETRIES` | `3` | Retries on schema validation failure |
| `GENERATION_TEMPERATURE` | `0.3` | Generation randomness (0=deterministic) |

---

## Hallucination Prevention

The pipeline enforces three independent layers of hallucination prevention:

1. **Extraction prompt** — Explicitly forbids inferring any attribute not stated by the artisan (e.g., no assuming "Punjab" for Phulkari, no assuming "Cotton" for a dupatta).
2. **Generation prompt** — Generator receives only `ProductFacts`, never the raw transcript. Any null fact is omitted.
3. **Factual validator** — Rule-based forbidden phrase scan + LLM cross-check between facts and description. Auto-regenerates if unsupported claims are found.

---

## License

MIT License
