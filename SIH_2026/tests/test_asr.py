"""
tests/test_asr.py
~~~~~~~~~~~~~~~~~~

Unit tests for ASR providers (mocked — no model loading required).
"""

from unittest.mock import MagicMock, patch

import pytest

from artisan_ai.asr.base import ASRProvider, TranscriptResult
from artisan_ai.asr.whisper_asr import WhisperASR


class TestTranscriptResult:
    def test_basic_creation(self):
        result = TranscriptResult(
            transcript="ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ",
            language_code="pa",
            language_name="Punjabi",
        )
        assert result.transcript == "ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ"
        assert result.language_code == "pa"
        assert result.language_name == "Punjabi"
        assert result.confidence is None
        assert result.model_name == ""

    def test_with_confidence(self):
        result = TranscriptResult(
            transcript="नमस्ते",
            language_code="hi",
            language_name="Hindi",
            confidence=0.95,
            model_name="whisper-large-v3",
        )
        assert result.confidence == 0.95
        assert result.model_name == "whisper-large-v3"


class TestASRProviderInterface:
    """Ensure the abstract interface is enforced."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            ASRProvider()  # type: ignore[abstract]

    def test_custom_provider_must_implement_transcribe(self):
        class IncompleteProvider(ASRProvider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_valid_custom_provider(self):
        class MockASR(ASRProvider):
            def transcribe(self, audio_path: str) -> TranscriptResult:
                return TranscriptResult(
                    transcript="Test transcript",
                    language_code="en",
                    language_name="English",
                )

        asr = MockASR()
        result = asr.transcribe("dummy.wav")
        assert result.transcript == "Test transcript"
        assert result.language_code == "en"


class TestWhisperASR:
    """Tests for WhisperASR with mocked whisper library."""

    def test_init_defaults(self):
        asr = WhisperASR()
        assert asr.model_size == "large-v3"
        assert asr.device == "cpu"
        assert asr.language is None
        assert asr._model is None

    def test_init_custom(self):
        asr = WhisperASR(model_size="medium", device="cuda", language="hi")
        assert asr.model_size == "medium"
        assert asr.device == "cuda"
        assert asr.language == "hi"

    def test_transcribe_with_mock_openai_whisper(self):
        """Test _transcribe_openai with a mocked whisper result."""
        pytest.importorskip("whisper", reason="openai-whisper not installed")
        asr = WhisperASR(model_size="tiny", device="cpu")
        asr._backend = "openai-whisper"

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": " ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ",
            "language": "pa",
            "segments": [{"avg_logprob": -0.2}],
        }
        asr._model = mock_model

        result = asr._transcribe_openai("dummy.wav")

        assert result.transcript == "ਇਹ ਫੁਲਕਾਰੀ ਦਾ ਦੁਪੱਟਾ ਹੈ"
        assert result.language_code == "pa"
        assert result.language_name == "Punjabi"
        assert result.confidence is not None
        assert result.model_name == "whisper-tiny"

    def test_transcribe_english_passthrough(self):
        """English audio should be returned without translation."""
        pytest.importorskip("whisper", reason="openai-whisper not installed")
        asr = WhisperASR(model_size="tiny", device="cpu")
        asr._backend = "openai-whisper"

        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": " This is a handmade shawl.",
            "language": "en",
            "segments": [],
        }
        asr._model = mock_model

        result = asr._transcribe_openai("english_audio.wav")
        assert result.language_code == "en"
        assert "handmade shawl" in result.transcript
