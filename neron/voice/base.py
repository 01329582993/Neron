"""Abstract contracts and models for the modular Voice Pipeline."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AudioDeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float


class AudioDeviceManager(ABC):
    """Abstract interface for enumerating and inspecting audio hardware."""

    @abstractmethod
    def list_input_devices(self) -> List[AudioDeviceInfo]:
        pass

    @abstractmethod
    def list_output_devices(self) -> List[AudioDeviceInfo]:
        pass

    @abstractmethod
    def get_default_input_device(self) -> Optional[AudioDeviceInfo]:
        pass


class VADEngine(ABC):
    """Voice Activity Detection engine for detecting active speech."""

    @abstractmethod
    def is_speech(self, audio_chunk: bytes, sample_rate: int = 16000) -> bool:
        pass


class WakeWordEngine(ABC):
    """Wake-word detector interface (e.g. for 'Hey Neron')."""

    @abstractmethod
    def detect(self, audio_chunk: bytes) -> bool:
        pass

    @property
    @abstractmethod
    def wake_phrase(self) -> str:
        pass


class STTEngine(ABC):
    """Speech to Text engine interface."""

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> str:
        pass


class TTSEngine(ABC):
    """Text to Speech synthesizer interface."""

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def speak(self, text: str) -> bool:
        pass
