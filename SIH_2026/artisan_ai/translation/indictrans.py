"""
artisan_ai.translation.indictrans
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

IndicTrans2 translation provider.

Uses IndicTransToolkit.processor.IndicProcessor for pre/post-processing
and AutoTokenizer + AutoModelForSeq2SeqLM for inference — matching the
working test_indictrans.py standalone script exactly.

Setup
-----
1. ``git clone https://github.com/AI4Bharat/IndicTrans2.git``
2. ``pip install -e ./IndicTrans2/huggingface_interface``
   (installs IndicTransToolkit + supporting HuggingFace interface)
3. Model downloads automatically from HuggingFace on first use.

Reference
---------
https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
"""

from __future__ import annotations

import logging
import re
from typing import Any

from artisan_ai.translation.base import TranslationProvider, TranslationResult

logger = logging.getLogger(__name__)

# ISO 639-1 -> FLORES-200 mapping required by IndicProcessor
ISO_TO_FLORES: dict[str, str] = {
    "hi": "hin_Deva",
    "pa": "pan_Guru",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "bn": "ben_Beng",
    "mr": "mar_Deva",
    "gu": "guj_Gujr",
    "kn": "kan_Knda",
    "ml": "mal_Mlym",
    "or": "ory_Orya",
    "en": "eng_Latn",
    "ur": "urd_Arab",
    "as": "asm_Beng",
    "sa": "san_Deva",
}


def _iso_to_flores(code: str) -> str:
    """Convert an ISO 639-1 code to its FLORES-200 equivalent."""
    flores = ISO_TO_FLORES.get(code)
    if not flores:
        raise ValueError(
            f"No FLORES-200 mapping for ISO 639-1 code {code!r}. "
            f"Supported codes: {sorted(ISO_TO_FLORES.keys())}"
        )
    return flores


def _split_sentences(text: str) -> list[str]:
    """Split on sentence-ending punctuation (includes Devanagari danda \u0964)."""
    sentences = re.split(r"(?<=[\u0964.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


class IndicTransProvider(TranslationProvider):
    """Translation provider backed by AI4Bharat IndicTrans2.

    The model is loaded **once** on first use and kept in memory for all
    subsequent requests — no repeated downloads or load times per request.

    Parameters
    ----------
    model_name:
        HuggingFace model ID.
        Defaults to ``ai4bharat/indictrans2-indic-en-dist-200M``.
    device:
        ``"cpu"`` or ``"cuda"``. Auto-detected when ``None``.
    num_beams:
        Beam width for generation.  ``1`` = greedy (fastest),
        ``5`` = beam search (better quality).  Defaults to ``5``.
    quantization:
        ``"4-bit"`` or ``"8-bit"`` for GPU memory saving.
        Empty string (default) = full precision.
    """

    def __init__(
        self,
        model_name: str = "ai4bharat/indictrans2-indic-en-dist-200M",
        device: str | None = None,
        num_beams: int = 1,  # IndicTrans2 model requires greedy (1); beam search causes AttributeError
        quantization: str = "",
        use_cache = False,
    ) -> None:
        self.model_name = model_name
        self.num_beams = num_beams
        self.quantization = quantization
        self.use_cache = use_cache

        if device is None:
            import torch  # type: ignore[import]
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Lazy-loaded on first translate() call
        self._model: Any = None
        self._tokenizer: Any = None
        self._processor: Any = None

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Load model, tokenizer, and IndicProcessor. No-op after first call."""
        if self._model is not None:
            return

        try:
            from IndicTransToolkit.processor import IndicProcessor  # type: ignore[import]
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "IndicTrans2 dependencies are not installed.\n"
                "Run:\n"
                "  git clone https://github.com/AI4Bharat/IndicTrans2.git\n"
                "  pip install -e ./IndicTrans2/huggingface_interface\n"
                "Or use the OpusMTProvider fallback."
            ) from exc

        logger.info(
            "Loading IndicTrans2 model %r on %s ...", self.model_name, self.device
        )

        # Tokenizer
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=True,
        )

        # Model (with optional quantization for GPU memory saving)
        model_kwargs: dict[str, Any] = {"trust_remote_code": True}
        if self.quantization == "4-bit":
            from transformers import BitsAndBytesConfig  # type: ignore[import]
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_compute_dtype="float16"
            )
        elif self.quantization == "8-bit":
            from transformers import BitsAndBytesConfig  # type: ignore[import]
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_8bit=True
            )

        self._model = AutoModelForSeq2SeqLM.from_pretrained(
            self.model_name, **model_kwargs
        ).to(self.device)
        self._model.eval()

        # IndicProcessor: script normalisation, punctuation, language tags
        self._processor = IndicProcessor(inference=True)

        logger.info("IndicTrans2 model loaded.")

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

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
            Source text in any supported Indic language.
        source_language:
            ISO 639-1 source code (e.g. ``"pa"`` for Punjabi).
        target_language:
            ISO 639-1 target code.  Must be ``"en"`` for the 200M model.

        Returns
        -------
        TranslationResult
        """
        # Short-circuit before loading the model for empty input
        if not text.strip():
            return TranslationResult(
                translated_text="",
                source_language=source_language,
                target_language=target_language,
                model_name=self.model_name,
            )

        self._load_model()  # No-op after first call

        src_flores = _iso_to_flores(source_language)
        tgt_flores = _iso_to_flores(target_language)

        logger.info(
            "Translating %s -> %s via IndicTrans2 ...", src_flores, tgt_flores
        )

        import torch  # type: ignore[import]

        sentences = _split_sentences(text)

        # 1. Pre-process: normalise script, insert language tags
        processed = self._processor.preprocess_batch(
            sentences,
            src_lang=src_flores,
            tgt_lang=tgt_flores,
        )

        # 2. Tokenize the whole batch at once
        inputs = self._tokenizer(
            processed,
            padding="longest",
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        # 3. Generate translations
        with torch.no_grad():
            generated_tokens = self._model.generate(
                **inputs,
                num_beams=self.num_beams,
                num_return_sequences=1,
                max_length=256,
                use_cache=self.use_cache,
            )

        # 4. Decode token ids -> strings
        decoded = self._tokenizer.batch_decode(
            generated_tokens,
            skip_special_tokens=True,
        )

        # 5. Post-process: remove model artifacts
        translations = self._processor.postprocess_batch(decoded, lang=tgt_flores)

        translated_text = " ".join(translations).strip()
        logger.info("Translation complete (%d chars).", len(translated_text))

        return TranslationResult(
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
            model_name=self.model_name,
        )
