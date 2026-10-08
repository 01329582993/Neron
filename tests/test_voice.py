"""Unit tests for the modular voice pipeline."""

import pytest
from neron.core.agent.base import NeronAgent
from neron.core.state.models import TaskState
from neron.voice.pipeline import VoicePipeline
from neron.voice.speech_to_text.engine import MockSTTEngine
from neron.voice.text_to_speech.engine import SystemTTSEngine
from neron.voice.wake_word.engine import SimpleWakeWordDetector


def test_wake_word_phrase_detection():
    detector = SimpleWakeWordDetector(phrase="hey neron")
    assert detector.detect_phrase_in_text("Hey Neron, open notepad") is True
    assert detector.detect_phrase_in_text("Neron, what is using my ram?") is True
    assert detector.detect_phrase_in_text("Hello world") is False


def test_voice_pipeline_input_cleaning():
    pipeline = VoicePipeline()
    assert pipeline.clean_voice_input("Hey Neron, open Chrome") == "open Chrome"
    assert pipeline.clean_voice_input("Neron! Please find my project") == "find my project"
    assert pipeline.clean_voice_input("Can you check my ram") == "check my ram"


def test_voice_pipeline_end_to_end_execution():
    class SilentTTSEngine(SystemTTSEngine):
        def speak(self, text: str) -> bool:
            return True

    stt = MockSTTEngine(default_text="Hey Neron, check my ram")
    tts = SilentTTSEngine()
    pipeline = VoicePipeline(stt_engine=stt, tts_engine=tts)

    plan = pipeline.process_voice_command(b"fake_audio_bytes", speak_response=True)
    assert plan is not None
    assert plan.state == TaskState.COMPLETED
    assert plan.steps[0].tool_name == "system.telemetry"


def test_system_tts_availability():
    tts = SystemTTSEngine()
    # On Windows, native SAPI is always available
    assert tts.is_available() is True
