"""Configuration loader and manager for Neron."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from neron.config.schema import (
    AIConfig,
    MemoryConfig,
    NeronConfig,
    OllamaConfig,
    OSConfig,
    OpenAICompatibleConfig,
    PluginConfig,
    SecurityConfig,
    SystemConfig,
    VoiceConfig,
)
from neron.utils.logger import get_logger

logger = get_logger("config")


class ConfigManager:
    """Loads, validates, and serves application configuration."""

    DEFAULT_CONFIG_PATH = Path("config/neron.yaml")

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config: NeronConfig = self._load()

    def _load(self) -> NeronConfig:
        """Load configuration from file, applying environment overrides."""
        raw_data: Dict[str, Any] = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    raw_data = yaml.safe_load(f) or {}
                logger.debug(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to read {self.config_path}: {e}. Using defaults.")
        else:
            logger.debug(f"Config file not found at {self.config_path}. Using defaults.")

        return self._build_config_object(raw_data)

    def _build_config_object(self, data: Dict[str, Any]) -> NeronConfig:
        """Construct NeronConfig dataclass hierarchy from raw dict."""
        sys_data = data.get("system", {})
        sec_data = data.get("security", {})
        ai_data = data.get("ai", {})
        voice_data = data.get("voice", {})
        mem_data = data.get("memory", {})
        os_data = data.get("os", {})
        plug_data = data.get("plugins", {})

        system = SystemConfig(
            app_name=sys_data.get("app_name", "Neron"),
            environment=os.getenv("NERON_ENV", sys_data.get("environment", "development")),
            data_dir=sys_data.get("data_dir", "data"),
            logs_dir=sys_data.get("logs_dir", "logs"),
            log_level=os.getenv("NERON_LOG_LEVEL", sys_data.get("log_level", "INFO")),
            audit_db_path=sys_data.get("audit_db_path", "data/audit.db"),
        )

        security = SecurityConfig(
            profile=os.getenv("NERON_SECURITY_PROFILE", sec_data.get("profile", "STANDARD")),
            emergency_stop_shortcut=sec_data.get("emergency_stop_shortcut", "ctrl+alt+n"),
            custom_policies=sec_data.get("custom_policies", {}),
        )

        ollama_data = ai_data.get("ollama", {})
        ollama = OllamaConfig(
            host=os.getenv("OLLAMA_HOST", ollama_data.get("host", "http://localhost:11434")),
            model=os.getenv("OLLAMA_MODEL", ollama_data.get("model", "llama3.2:3b")),
            timeout=ollama_data.get("timeout", 30),
            temperature=ollama_data.get("temperature", 0.2),
        )

        openai_data = ai_data.get("openai_compatible", {})
        openai_compat = OpenAICompatibleConfig(
            enabled=openai_data.get("enabled", False),
            base_url=os.getenv("OPENAI_BASE_URL", openai_data.get("base_url", "http://localhost:8000/v1")),
            api_key=os.getenv("OPENAI_API_KEY", openai_data.get("api_key", "")),
            model=os.getenv("OPENAI_MODEL", openai_data.get("model", "default")),
        )

        ai = AIConfig(
            default_provider=os.getenv("NERON_AI_PROVIDER", ai_data.get("default_provider", "ollama")),
            fallback_provider=ai_data.get("fallback_provider", "local_heuristic"),
            auto_offline_fallback=ai_data.get("auto_offline_fallback", True),
            ollama=ollama,
            openai_compatible=openai_compat,
        )

        voice = VoiceConfig(
            enabled=voice_data.get("enabled", False),
            wake_word=voice_data.get("wake_word", "hey neron"),
            sample_rate=voice_data.get("sample_rate", 16000),
            vad_sensitivity=voice_data.get("vad_sensitivity", 2),
            stt_provider=voice_data.get("stt_provider", "whisper"),
            tts_provider=voice_data.get("tts_provider", "system"),
        )

        memory = MemoryConfig(
            enabled=mem_data.get("enabled", True),
            db_path=mem_data.get("db_path", "data/memory.db"),
            short_term_history_limit=mem_data.get("short_term_history_limit", 20),
        )

        os_cfg = OSConfig(
            process_poll_interval=os_data.get("process_poll_interval", 1.0),
            verify_actions=os_data.get("verify_actions", True),
            action_timeout_seconds=os_data.get("action_timeout_seconds", 15),
        )

        plugins = PluginConfig(
            directory=plug_data.get("directory", "plugins"),
            auto_discover=plug_data.get("auto_discover", True),
            enabled=plug_data.get("enabled", []),
        )

        return NeronConfig(
            version=data.get("version", "1.0"),
            system=system,
            security=security,
            ai=ai,
            voice=voice,
            memory=memory,
            os=os_cfg,
            plugins=plugins,
        )

    def reload(self) -> NeronConfig:
        """Reload configuration from disk."""
        self.config = self._load()
        return self.config
