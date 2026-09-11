"""
artisan_ai.audio.preprocessing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Modular audio preprocessing pipeline.

Steps (each independently replaceable):
  1. Format conversion  → .wav via pydub/ffmpeg
  2. Mono conversion    → merge stereo channels
  3. Resample           → 16 kHz (Whisper requirement)
  4. Loudness normalize → target -23 LUFS
  5. Silence trim       → remove leading/trailing silence using VAD
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac", ".aac"}
TARGET_SAMPLE_RATE = 16_000  # Hz  – Whisper requirement
TARGET_LOUDNESS_LUFS = -23.0


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class PreprocessedAudio:
    path: str          # Absolute path to the processed .wav file
    sample_rate: int   # Always TARGET_SAMPLE_RATE after preprocessing
    channels: int      # Always 1 (mono) after preprocessing
    duration_seconds: float
    original_path: str


# ── Step protocol (each step can be replaced) ─────────────────────────────────

class AudioStep(Protocol):
    def __call__(self, audio: "pydub.AudioSegment") -> "pydub.AudioSegment":
        ...


# ── Individual steps ──────────────────────────────────────────────────────────

def to_mono(audio: "pydub.AudioSegment") -> "pydub.AudioSegment":
    """Merge all channels into a single mono channel."""
    if audio.channels > 1:
        logger.debug("Converting %d-channel audio to mono.", audio.channels)
        audio = audio.set_channels(1)
    return audio


def resample(audio: "pydub.AudioSegment", target_rate: int = TARGET_SAMPLE_RATE) -> "pydub.AudioSegment":
    """Resample audio to target_rate Hz."""
    if audio.frame_rate != target_rate:
        logger.debug(
            "Resampling from %d Hz → %d Hz.", audio.frame_rate, target_rate
        )
        audio = audio.set_frame_rate(target_rate)
    return audio


def normalize_loudness(audio: "pydub.AudioSegment") -> "pydub.AudioSegment":
    """Normalize to -23 LUFS using pydub's simple dBFS-based normalization.

    Note: True LUFS normalization requires ``pyloudnorm``.  pydub's
    ``normalize()`` targets 0 dBFS which is too loud; we target a
    reasonable conversational level instead.
    """
    try:
        import pyloudnorm as pyln
        import numpy as np

        samples = (
            audio.get_array_of_samples()
        )
        data = np.array(samples, dtype=np.float32) / (2 ** 15)
        meter = pyln.Meter(audio.frame_rate)
        loudness = meter.integrated_loudness(data)
        if not (loudness == float("-inf")):
            gain_db = TARGET_LOUDNESS_LUFS - loudness
            audio = audio.apply_gain(gain_db)
            logger.debug("Applied %.1f dB loudness gain.", gain_db)
    except ImportError:
        # Fallback: simple peak normalization
        target_dbfs = -18.0
        change_in_dbfs = target_dbfs - audio.dBFS
        audio = audio.apply_gain(change_in_dbfs)
        logger.debug(
            "pyloudnorm not installed. Applied simple dBFS normalization."
        )
    return audio


def trim_silence(
    audio: "pydub.AudioSegment",
    silence_thresh_db: int = -40,
    min_silence_ms: int = 300,
    padding_ms: int = 150,
) -> "pydub.AudioSegment":
    """Remove leading/trailing silence and very long internal pauses."""
    from pydub.silence import detect_nonsilent

    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=min_silence_ms,
        silence_thresh=silence_thresh_db,
    )
    if not nonsilent_ranges:
        logger.warning("No non-silent segments detected. Returning audio as-is.")
        return audio

    start_ms = max(0, nonsilent_ranges[0][0] - padding_ms)
    end_ms = min(len(audio), nonsilent_ranges[-1][1] + padding_ms)
    trimmed = audio[start_ms:end_ms]
    logger.debug(
        "Trimmed silence: %.1fs → %.1fs",
        len(audio) / 1000,
        len(trimmed) / 1000,
    )
    return trimmed


# ── Main preprocessor ─────────────────────────────────────────────────────────

class AudioPreprocessor:
    """Runs an ordered sequence of audio preprocessing steps.

    Parameters
    ----------
    steps:
        List of callables that accept and return a ``pydub.AudioSegment``.
        Defaults to the recommended pipeline.
    output_dir:
        Directory for temporary WAV output.  Defaults to the system temp dir.
    """

    DEFAULT_STEPS = [to_mono, resample, normalize_loudness, trim_silence]

    def __init__(
        self,
        steps: list[AudioStep] | None = None,
        output_dir: str | None = None,
    ) -> None:
        self.steps = steps if steps is not None else self.DEFAULT_STEPS
        self.output_dir = output_dir or tempfile.gettempdir()

    def process(self, audio_path: str) -> PreprocessedAudio:
        """Preprocess *audio_path* and return a :class:`PreprocessedAudio`.

        Parameters
        ----------
        audio_path:
            Path to any audio file in a format supported by pydub/ffmpeg.

        Returns
        -------
        PreprocessedAudio
            Contains the path to the normalized WAV file and metadata.

        Raises
        ------
        FileNotFoundError
            If *audio_path* does not exist.
        ValueError
            If the file extension is not in ``SUPPORTED_FORMATS``.
        """
        path = Path(audio_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported audio format '{suffix}'. "
                f"Supported: {sorted(SUPPORTED_FORMATS)}"
            )

        try:
            from pydub import AudioSegment
        except ImportError as exc:
            raise ImportError(
                "pydub is required for audio preprocessing. "
                "Install with: pip install pydub"
            ) from exc

        logger.info("Loading audio: %s", path)
        audio = AudioSegment.from_file(str(path))
        logger.info(
            "Loaded: %.1fs, %d Hz, %d ch",
            len(audio) / 1000,
            audio.frame_rate,
            audio.channels,
        )

        # Apply each step in sequence
        for step in self.steps:
            audio = step(audio)

        # Export to a deterministic temp WAV path
        stem = path.stem
        out_path = os.path.join(self.output_dir, f"_artisan_{stem}_processed.wav")
        audio.export(out_path, format="wav")
        logger.info("Preprocessed audio saved: %s", out_path)

        return PreprocessedAudio(
            path=out_path,
            sample_rate=audio.frame_rate,
            channels=audio.channels,
            duration_seconds=len(audio) / 1000,
            original_path=str(path),
        )
