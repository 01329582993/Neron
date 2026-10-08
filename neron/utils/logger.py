"""Structured and sanitized logging subsystem for Neron."""

import logging
import os
import re
from pathlib import Path
from typing import Optional

try:
    import colorama
    from colorama import Fore, Style
    colorama.init(autoreset=True)
    _COLOR_AVAILABLE = True
except ImportError:
    _COLOR_AVAILABLE = False


# Patterns for sensitive data that should never appear in plaintext logs
SENSITIVE_PATTERNS = [
    re.compile(r"(api[_-]?key\s*[:=]\s*)['\"]?([a-zA-Z0-9_\-]{8,})['\"]?", re.IGNORECASE),
    re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*)['\"]?([^'\"\s]+)['\"]?", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)['\"]?([a-zA-Z0-9_\-]{8,})['\"]?", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*)['\"]?([^'\"\s]+)['\"]?", re.IGNORECASE),
]


def sanitize_message(message: str) -> str:
    """Sanitize sensitive patterns from log messages."""
    sanitized = str(message)
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
    return sanitized


class SanitizedFormatter(logging.Formatter):
    """Logging formatter that scrubs sensitive keys and values."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return sanitize_message(original)


class ColorConsoleFormatter(SanitizedFormatter):
    """Console formatter with color highlights by log level."""

    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN if _COLOR_AVAILABLE else "",
        logging.INFO: Fore.GREEN if _COLOR_AVAILABLE else "",
        logging.WARNING: Fore.YELLOW if _COLOR_AVAILABLE else "",
        logging.ERROR: Fore.RED if _COLOR_AVAILABLE else "",
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT if _COLOR_AVAILABLE else "",
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        reset = Style.RESET_ALL if _COLOR_AVAILABLE else ""
        formatted = super().format(record)
        return f"{color}{formatted}{reset}"


def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    log_filename: str = "neron.log"
) -> logging.Logger:
    """Configure system-wide logging with both file and console handlers."""
    root_logger = logging.getLogger("neron")
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on re-initialization
    if root_logger.handlers:
        return root_logger

    log_format = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(ColorConsoleFormatter(log_format, datefmt=date_format))
    root_logger.addHandler(console_handler)

    # File Handler
    try:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path / log_filename, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(SanitizedFormatter(log_format, datefmt=date_format))
        root_logger.addHandler(file_handler)
    except Exception as exc:
        print(f"[Neron Logger Warning] Could not initialize file logging: {exc}")

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Obtain a child logger under the neron namespace."""
    if not name.startswith("neron"):
        name = f"neron.{name}"
    return logging.getLogger(name)
