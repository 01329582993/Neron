"""Dynamic AI provider router with automated offline fallback."""

import time
from typing import Dict, List, Optional
from neron.ai.base import LLMProvider
from neron.ai.llm.heuristic import HeuristicProvider
from neron.ai.llm.ollama import OllamaProvider
from neron.ai.llm.openai_compatible import OpenAICompatibleProvider
from neron.config.schema import AIConfig
from neron.utils.logger import get_logger

logger = get_logger("ai.routing")


class AIRouter:
    """Manages interchangeable AI model backends and handles offline fallback."""

    def __init__(self, ai_config: Optional[AIConfig] = None):
        self.config = ai_config or AIConfig()
        self._providers: Dict[str, LLMProvider] = {}
        self._availability_cache: Dict[str, tuple[bool, float]] = {}
        self._cache_ttl_seconds = 10.0

        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Register supported providers based on configuration."""
        # 1. Ollama Local Provider
        ollama_cfg = self.config.ollama
        self.register_provider(
            OllamaProvider(
                host=ollama_cfg.host,
                model=ollama_cfg.model,
                timeout=ollama_cfg.timeout,
                temperature=ollama_cfg.temperature,
            )
        )

        # 2. OpenAI-Compatible Provider
        openai_cfg = self.config.openai_compatible
        if openai_cfg.enabled:
            self.register_provider(
                OpenAICompatibleProvider(
                    base_url=openai_cfg.base_url,
                    api_key=openai_cfg.api_key,
                    model=openai_cfg.model,
                )
            )

        # 3. Guaranteed Local Heuristic Fallback
        self.register_provider(HeuristicProvider())

    def register_provider(self, provider: LLMProvider) -> None:
        """Register a provider instance."""
        self._providers[provider.name] = provider
        logger.debug(f"Registered AI Provider '{provider.name}'")

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """Look up provider by name."""
        return self._providers.get(name)

    def is_provider_available(self, name: str, force_check: bool = False) -> bool:
        """Check availability with TTL caching to minimize ping overhead."""
        provider = self._providers.get(name)
        if not provider:
            return False

        now = time.time()
        cached = self._availability_cache.get(name)
        if not force_check and cached and (now - cached[1] < self._cache_ttl_seconds):
            return cached[0]

        available = provider.is_available()
        self._availability_cache[name] = (available, now)
        return available

    def get_active_provider(self) -> LLMProvider:
        """Select active provider, automatically falling back if preferred is unavailable."""
        default_name = self.config.default_provider

        # 1. Check default configured provider
        if default_name in self._providers and self.is_provider_available(default_name):
            return self._providers[default_name]

        # 2. If auto_offline_fallback is active, search for alternative available providers
        if self.config.auto_offline_fallback:
            for name, provider in self._providers.items():
                if name != default_name and self.is_provider_available(name):
                    logger.debug(f"Default provider '{default_name}' unavailable. Falling back to '{name}'.")
                    return provider

        # 3. Guaranteed fallback to heuristic engine
        return self._providers.get("heuristic", HeuristicProvider())

    def list_providers(self) -> List[str]:
        """Return names of all registered providers."""
        return list(self._providers.keys())

    def check_all_statuses(self) -> Dict[str, bool]:
        """Query availability status across all registered providers."""
        return {name: self.is_provider_available(name, force_check=True) for name in self._providers}
