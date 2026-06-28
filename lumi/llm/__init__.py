from __future__ import annotations

from lumi.config import ConfigError, LLMConfig
from lumi.llm.base import LLM
from lumi.llm.openai import OpenAIProvider


def create_llm(config: LLMConfig) -> LLM:
    if config.provider == "openai":
        return OpenAIProvider(config)
    raise ConfigError(f"unknown provider: {config.provider}")
