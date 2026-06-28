from __future__ import annotations

from lumi.config import ConfigError, LLMConfig, resolve_adapter
from lumi.events import EventBus
from lumi.llm.anthropic import AnthropicProvider
from lumi.llm.base import LLM
from lumi.llm.openai import OpenAIProvider
from lumi.tools.server.registry import ServerToolRegistry


def create_llm(
    config: LLMConfig,
    server_tools: ServerToolRegistry | None = None,
    events: EventBus | None = None,
) -> LLM:
    adapter = resolve_adapter(config.provider)
    if adapter == "openai":
        return OpenAIProvider(config)
    if adapter == "anthropic":
        return AnthropicProvider(config, server_tools=server_tools, events=events)
    raise ConfigError(f"unknown adapter: {adapter}")
