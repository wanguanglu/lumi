from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from lumi.messages import Message, ToolCall


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    usage: TokenUsage | None
    raw: dict
    server_tool_uses: int = 0
    raw_blocks: list[dict] | None = None
    prior_assistant_blocks: list[list[dict]] = field(default_factory=list)


class LLMError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class LLMRateLimitError(LLMError):
    pass


class LLMAuthError(LLMError):
    pass


class LLM(Protocol):
    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse: ...
