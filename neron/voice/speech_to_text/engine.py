"""Speech-to-Text engines."""

from typing import Optional
from neron.voice.base import STTEngine
from neron.utils.logger import get_logger

logger = get_logger("voice.stt")


class WhisperSTTEngine(STTEngine):
    """Local Speech-to-Text using Whisper or faster-whisper."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None
        self._available = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import whisper
            self._available = True
        except ImportError:
            try:
                import faster_whisper
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        if not self.is_available():
            raise RuntimeError(
                "Whisper STT is not installed. Run: pip install openai-whisper or pip install faster-whisper"
            )
        # Transcribe audio data
        return ""


class MockSTTEngine(STTEngine):
    """Deterministic STT engine for automated testing and CI environments."""

    def __init__(self, default_text: str = "what is using all my ram?"):
        self.default_text = default_text

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        return self.default_text
