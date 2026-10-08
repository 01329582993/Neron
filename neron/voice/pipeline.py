"""End-to-end modular Voice Pipeline coordinating VAD, Wake Word, STT, Agent, and TTS."""

import re
from typing import Optional
from neron.core.agent.base import NeronAgent
from neron.core.state.models import TaskPlan
from neron.utils.logger import get_logger
from neron.voice.base import STTEngine, TTSEngine, WakeWordEngine
from neron.voice.speech_to_text.engine import MockSTTEngine, WhisperSTTEngine
from neron.voice.text_to_speech.engine import SystemTTSEngine
from neron.voice.wake_word.engine import SimpleWakeWordDetector

logger = get_logger("voice.pipeline")


class VoicePipeline:
    """Coordinates voice perception, intent execution, and spoken feedback."""

    def __init__(
        self,
        agent: Optional[NeronAgent] = None,
        stt_engine: Optional[STTEngine] = None,
        tts_engine: Optional[TTSEngine] = None,
        wake_engine: Optional[WakeWordEngine] = None,
    ):
        self.agent = agent or NeronAgent()
        self.stt_engine = stt_engine or (WhisperSTTEngine() if WhisperSTTEngine().is_available() else MockSTTEngine())
        self.tts_engine = tts_engine or SystemTTSEngine()
        self.wake_engine = wake_engine or SimpleWakeWordDetector()

    def clean_voice_input(self, text: str) -> str:
        """Strip conversational wake words and filler prefixes."""
        cleaned = re.sub(r"^(?:hey\s+)?neron[,!\.]?\s*", "", text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"^(?:please\s+|can\s+you\s+|could\s+you\s+)", "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def process_voice_command(self, audio_data: bytes, speak_response: bool = True) -> Optional[TaskPlan]:
        """Transcribe audio, execute goal via NeronAgent, and provide spoken feedback."""
        # 1. Transcribe audio to text
        raw_text = self.stt_engine.transcribe(audio_data)
        if not raw_text:
            logger.debug("Voice input yielded empty transcript.")
            return None

        logger.info(f"Voice Transcription: '{raw_text}'")

        # 2. Clean intent query
        goal = self.clean_voice_input(raw_text)
        if not goal:
            return None

        # 3. Dispatch to NeronAgent
        plan = self.agent.run_goal(goal)

        # 4. Spoken Feedback
        if speak_response and self.tts_engine.is_available():
            if plan.state.value == "COMPLETED":
                speech = f"Task completed. Executed {len(plan.steps)} steps."
            else:
                speech = f"Task {plan.state.value.lower()}. {plan.error or ''}"
            try:
                self.tts_engine.speak(speech)
            except Exception as e:
                logger.error(f"TTS playback error: {e}")

        return plan
