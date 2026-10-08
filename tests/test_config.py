"""Unit tests for configuration manager and schema validation."""

import os
from pathlib import Path
import pytest
from neron.config.manager import ConfigManager
from neron.config.schema import NeronConfig


def test_default_config_loading():
    mgr = ConfigManager()
    cfg = mgr.config
    assert isinstance(cfg, NeronConfig)
    assert cfg.system.app_name == "Neron"
    assert cfg.security.profile in ("SAFE", "STANDARD", "POWER_USER", "CUSTOM")
    assert cfg.ai.default_provider == "ollama"
    assert cfg.memory.enabled is True


def test_environment_variable_overrides(monkeypatch):
    monkeypatch.setenv("NERON_SECURITY_PROFILE", "SAFE")
    monkeypatch.setenv("NERON_AI_PROVIDER", "openai_compatible")
    monkeypatch.setenv("OLLAMA_MODEL", "custom-model:latest")

    mgr = ConfigManager()
    cfg = mgr.config
    assert cfg.security.profile == "SAFE"
    assert cfg.ai.default_provider == "openai_compatible"
    assert cfg.ai.ollama.model == "custom-model:latest"
