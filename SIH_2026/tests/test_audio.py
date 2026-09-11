"""
tests/test_audio.py
~~~~~~~~~~~~~~~~~~~~

Unit tests for audio preprocessing.
"""

import os
import tempfile
import wave
import struct
import pytest

from artisan_ai.audio.preprocessing import (
    AudioPreprocessor,
    to_mono,
    resample,
    trim_silence,
    SUPPORTED_FORMATS,
    TARGET_SAMPLE_RATE,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _create_dummy_wav(path: str, channels: int = 1, sample_rate: int = 44100, duration_ms: int = 1000) -> None:
    """Create a minimal valid WAV file with a sine-like signal."""
    import math

    n_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        for i in range(n_samples):
            # Simple 440 Hz sine wave
            value = int(32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
            for _ in range(channels):
                wf.writeframes(struct.pack("<h", value))


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestSupportedFormats:
    def test_wav_in_supported(self):
        assert ".wav" in SUPPORTED_FORMATS

    def test_mp3_in_supported(self):
        assert ".mp3" in SUPPORTED_FORMATS

    def test_m4a_in_supported(self):
        assert ".m4a" in SUPPORTED_FORMATS

    def test_unsupported_format(self, tmp_path):
        # Create an actual file with an unsupported extension
        fake = tmp_path / "audio.xyz"
        fake.write_text("dummy")
        preprocessor = AudioPreprocessor()
        with pytest.raises(ValueError, match="Unsupported audio format"):
            preprocessor.process(str(fake))

    def test_file_not_found(self):
        preprocessor = AudioPreprocessor()
        with pytest.raises(FileNotFoundError):
            preprocessor.process("nonexistent_audio.wav")


class TestAudioSteps:
    """Test individual preprocessing steps with pydub."""

    @pytest.fixture()
    def mono_segment(self):
        try:
            from pydub import AudioSegment
        except ImportError:
            pytest.skip("pydub not installed")
        return AudioSegment.silent(duration=1000, frame_rate=44100)

    @pytest.fixture()
    def stereo_segment(self):
        try:
            from pydub import AudioSegment
        except ImportError:
            pytest.skip("pydub not installed")
        audio = AudioSegment.silent(duration=1000, frame_rate=44100)
        return audio.set_channels(2)

    def test_to_mono_from_stereo(self, stereo_segment):
        result = to_mono(stereo_segment)
        assert result.channels == 1

    def test_to_mono_already_mono(self, mono_segment):
        result = to_mono(mono_segment)
        assert result.channels == 1

    def test_resample(self, mono_segment):
        result = resample(mono_segment, target_rate=TARGET_SAMPLE_RATE)
        assert result.frame_rate == TARGET_SAMPLE_RATE

    def test_resample_already_correct_rate(self):
        try:
            from pydub import AudioSegment
        except ImportError:
            pytest.skip("pydub not installed")
        audio = AudioSegment.silent(duration=500, frame_rate=TARGET_SAMPLE_RATE)
        result = resample(audio)
        assert result.frame_rate == TARGET_SAMPLE_RATE


class TestAudioPreprocessor:
    """Integration tests for the full preprocessor."""

    def test_process_mono_wav(self, tmp_path):
        try:
            from pydub import AudioSegment
        except ImportError:
            pytest.skip("pydub not installed")

        wav_path = str(tmp_path / "test_mono.wav")
        _create_dummy_wav(wav_path, channels=1, sample_rate=44100)

        preprocessor = AudioPreprocessor(output_dir=str(tmp_path))
        result = preprocessor.process(wav_path)

        assert os.path.exists(result.path)
        assert result.channels == 1
        assert result.sample_rate == TARGET_SAMPLE_RATE
        assert result.duration_seconds > 0
        assert result.original_path == wav_path

    def test_process_stereo_wav(self, tmp_path):
        try:
            from pydub import AudioSegment
        except ImportError:
            pytest.skip("pydub not installed")

        wav_path = str(tmp_path / "test_stereo.wav")
        _create_dummy_wav(wav_path, channels=2, sample_rate=44100)

        preprocessor = AudioPreprocessor(output_dir=str(tmp_path))
        result = preprocessor.process(wav_path)

        assert result.channels == 1  # Should be converted to mono
        assert result.sample_rate == TARGET_SAMPLE_RATE

    def test_custom_steps(self, tmp_path):
        """Preprocessor should work with a custom step list."""
        try:
            from pydub import AudioSegment
        except ImportError:
            pytest.skip("pydub not installed")

        wav_path = str(tmp_path / "test_custom.wav")
        _create_dummy_wav(wav_path)

        # Use only mono conversion + resample (no normalize/trim)
        preprocessor = AudioPreprocessor(
            steps=[to_mono, resample],
            output_dir=str(tmp_path),
        )
        result = preprocessor.process(wav_path)
        assert result.channels == 1
        assert result.sample_rate == TARGET_SAMPLE_RATE
