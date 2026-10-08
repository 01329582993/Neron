"""Modular voice input/output subsystem."""

from neron.voice.base import (
    AudioDeviceInfo,
    AudioDeviceManager,
    STTEngine,
    TTSEngine,
    VADEngine,
    WakeWordEngine,
)
from neron.voice.pipeline import VoicePipeline
from neron.voice.speech_to_text.engine import MockSTTEngine, WhisperSTTEngine
from neron.voice.text_to_speech.engine import SystemTTSEngine
from neron.voice.wake_word.engine import SimpleWakeWordDetector

__all__ = [
    "AudioDeviceInfo",
    "AudioDeviceManager",
    "VADEngine",
    "WakeWordEngine",
    "STTEngine",
    "TTSEngine",
    "VoicePipeline",
    "WhisperSTTEngine",
    "MockSTTEngine",
    "SystemTTSEngine",
    "SimpleWakeWordDetector",
]
