"""Abstract base contracts for desktop computer control and vision."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class CursorPosition:
    x: int
    y: int


@dataclass
class ScreenResolution:
    width: int
    height: int


@dataclass
class BoundingBox:
    x: int
    y: int
    width: int
    height: int


class MouseController(ABC):
    """Abstract interface for desktop mouse control."""

    @abstractmethod
    def get_position(self) -> CursorPosition:
        pass

    @abstractmethod
    def move_to(self, x: int, y: int) -> bool:
        pass

    @abstractmethod
    def click(self, button: str = "left", count: int = 1) -> bool:
        pass

    @abstractmethod
    def scroll(self, clicks: int) -> bool:
        pass


class KeyboardController(ABC):
    """Abstract interface for desktop keyboard input."""

    @abstractmethod
    def type_text(self, text: str) -> bool:
        pass

    @abstractmethod
    def press_key(self, key_name: str) -> bool:
        pass

    @abstractmethod
    def hotkey(self, *keys: str) -> bool:
        pass


class ScreenCapture(ABC):
    """Abstract interface for screen capture and pixel sampling."""

    @abstractmethod
    def get_resolution(self) -> ScreenResolution:
        pass

    @abstractmethod
    def capture(self, output_path: Optional[str] = None) -> bytes:
        pass
