from __future__ import annotations

from lumi.config import ConfigError, LLMConfig, resolve_adapter
from lumi.events import EventBus
from lumi.llm.anthropic import AnthropicProvider
from lumi.llm.base import LLM
from lumi.llm.openai import OpenAIProvider


def create_llm(
    config: LLMConfig,
    events: EventBus | None = None,
) -> LLM:
    adapter = resolve_adapter(config.provider)
    if adapter == "openai":
        return OpenAIProvider(config)
    if adapter == "anthropic":
        return AnthropicProvider(config, events=events)
    raise ConfigError(f"unknown adapter: {adapter}")
