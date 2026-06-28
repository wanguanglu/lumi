from __future__ import annotations

import json

import httpx

from lumi.config import LLMConfig
from lumi.llm.base import LLMAuthError, LLMError, LLMRateLimitError, LLMResponse, TokenUsage
from lumi.messages import AssistantMessage, Message, ToolCall, to_api_format


class OpenAIProvider:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = httpx.Client(timeout=config.timeout)

    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }
        body: dict = {
            "model": self.config.model,
            "messages": to_api_format(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            body["tools"] = tools

        try:
            response = self._client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as e:
            raise LLMError(f"request timed out after {self.config.timeout}s") from e
        except httpx.HTTPError as e:
            raise LLMError(f"HTTP error: {e}") from e

        if response.status_code == 401:
            raise LLMAuthError("authentication failed", status_code=401, body=response.text)
        if response.status_code == 429:
            raise LLMRateLimitError("rate limit exceeded", status_code=429, body=response.text)
        if response.status_code >= 400:
            raise LLMError(
                f"API error {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )

        data = response.json()
        return self._parse_response(data)

    def _parse_response(self, data: dict) -> LLMResponse:
        choice = data["choices"][0]["message"]
        tool_calls: list[ToolCall] = []

        for tc in choice.get("tool_calls") or []:
            fn = tc["function"]
            raw_args = fn.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                arguments = {"_raw": raw_args}

            tool_calls.append(
                ToolCall(id=tc["id"], name=fn["name"], arguments=arguments)
            )

        usage = None
        if "usage" in data:
            u = data["usage"]
            usage = TokenUsage(
                prompt_tokens=u.get("prompt_tokens", 0),
                completion_tokens=u.get("completion_tokens", 0),
                total_tokens=u.get("total_tokens", 0),
            )

        return LLMResponse(
            content=choice.get("content"),
            tool_calls=tool_calls,
            usage=usage,
            raw=data,
        )

    def to_assistant_message(self, response: LLMResponse) -> AssistantMessage:
        return AssistantMessage(content=response.content, tool_calls=response.tool_calls)
