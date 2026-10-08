"""Configuration schema and data models for Neron."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SystemConfig:
    app_name: str = "Neron"
    environment: str = "development"
    data_dir: str = "data"
    logs_dir: str = "logs"
    log_level: str = "INFO"
    audit_db_path: str = "data/audit.db"


@dataclass
class SecurityConfig:
    profile: str = "STANDARD"  # SAFE, STANDARD, POWER_USER, CUSTOM
    emergency_stop_shortcut: str = "ctrl+alt+n"
    custom_policies: Dict[str, bool] = field(default_factory=dict)


@dataclass
class OllamaConfig:
    host: str = "http://localhost:11434"
    model: str = "llama3.2:3b"
    timeout: int = 30
    temperature: float = 0.2


@dataclass
class OpenAICompatibleConfig:
    enabled: bool = False
    base_url: str = "http://localhost:8000/v1"
    api_key: str = ""
    model: str = "default"


@dataclass
class AIConfig:
    default_provider: str = "ollama"
    fallback_provider: str = "local_heuristic"
    auto_offline_fallback: bool = True
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    openai_compatible: OpenAICompatibleConfig = field(default_factory=OpenAICompatibleConfig)


@dataclass
class VoiceConfig:
    enabled: bool = False
    wake_word: str = "hey neron"
    sample_rate: int = 16000
    vad_sensitivity: int = 2
    stt_provider: str = "whisper"
    tts_provider: str = "system"


@dataclass
class MemoryConfig:
    enabled: bool = True
    db_path: str = "data/memory.db"
    short_term_history_limit: int = 20


@dataclass
class OSConfig:
    process_poll_interval: float = 1.0
    verify_actions: bool = True
    action_timeout_seconds: int = 15


@dataclass
class PluginConfig:
    directory: str = "plugins"
    auto_discover: bool = True
    enabled: List[str] = field(default_factory=list)


@dataclass
class NeronConfig:
    version: str = "1.0"
    system: SystemConfig = field(default_factory=SystemConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    os: OSConfig = field(default_factory=OSConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)
