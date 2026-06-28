from __future__ import annotations

from lumi.config import ConfigError, LLMConfig, resolve_adapter
from lumi.llm.base import LLM
from lumi.llm.openai import OpenAIProvider


def create_llm(config: LLMConfig) -> LLM:
    adapter = resolve_adapter(config.provider)
    if adapter == "openai":
        return OpenAIProvider(config)
    raise ConfigError(f"unknown adapter: {adapter}")
