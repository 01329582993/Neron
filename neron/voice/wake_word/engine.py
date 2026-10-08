"""Wake word detection engine."""

import re
from neron.voice.base import WakeWordEngine


class SimpleWakeWordDetector(WakeWordEngine):
    """Detects wake word phrase ('Hey Neron') from text or audio cues."""

    def __init__(self, phrase: str = "hey neron"):
        self._phrase = phrase.lower()

    @property
    def wake_phrase(self) -> str:
        return self._phrase

    def detect(self, audio_chunk: bytes) -> bool:
        """Energy threshold check on raw audio frame."""
        if not audio_chunk:
            return False
        # Calculate root mean square energy
        import audioop
        try:
            rms = audioop.rms(audio_chunk, 2)
            return rms > 1500  # Voice energy presence threshold
        except Exception:
            return len(audio_chunk) > 100

    def detect_phrase_in_text(self, transcript: str) -> bool:
        """Check if wake word exists in transcribed string."""
        lower = transcript.lower()
        return bool(re.search(r"\b(?:hey\s+)?neron\b", lower))
