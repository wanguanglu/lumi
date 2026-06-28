from __future__ import annotations

import json

import httpx

from lumi.config import LLMConfig
from lumi.events import EventBus
from lumi.llm.base import LLMError, LLMResponse
from lumi.llm.messages_anthropic import (
    build_anthropic_request_body,
    count_search_results,
    count_server_tool_uses,
    extract_client_tool_calls,
    extract_text_blocks,
    has_server_tool_activity,
    parse_anthropic_response,
    split_system_messages,
    to_anthropic_messages,
)
from lumi.llm.openai import _raise_api_error
from lumi.messages import Message

MAX_INNER_STEPS = 5


class AnthropicProvider:
    adapter = "anthropic"

    def __init__(
        self,
        config: LLMConfig,
        events: EventBus | None = None,
    ) -> None:
        self.config = config
        self.events = events
        self._client = httpx.Client(timeout=config.timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AnthropicProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        system, _ = split_system_messages(messages)
        anthropic_messages = to_anthropic_messages(messages)
        total_server_uses = 0
        prior_assistant_blocks: list[list[dict]] = []

        for _ in range(MAX_INNER_STEPS):
            body = build_anthropic_request_body(
                self.config, anthropic_messages, tools, system=system
            )
            data = self._post(body)
            content = data.get("content") or []
            stop_reason = data.get("stop_reason")
            server_uses = count_server_tool_uses(content)
            total_server_uses += server_uses

            if server_uses and self.events:
                for block in content:
                    if block.get("type") == "server_tool_use":
                        self.events.emit(
                            "server_tool_start",
                            name=block.get("name", "web_search"),
                            type=block.get("type", ""),
                        )
                self.events.emit(
                    "server_tool_end",
                    name="web_search",
                    results_count=count_search_results(content),
                )

            client_calls = extract_client_tool_calls(content)
            if client_calls:
                response = parse_anthropic_response(data)
                response.server_tool_uses = total_server_uses
                response.prior_assistant_blocks = prior_assistant_blocks
                return response

            if has_server_tool_activity(content) and (
                stop_reason != "end_turn" or not extract_text_blocks(content)
            ):
                anthropic_messages.append({"role": "assistant", "content": content})
                prior_assistant_blocks.append(list(content))
                continue

            response = parse_anthropic_response(data)
            response.server_tool_uses = total_server_uses
            response.prior_assistant_blocks = prior_assistant_blocks
            return response

        raise LLMError(f"max inner steps ({MAX_INNER_STEPS}) exceeded for server tools")

    def _post(self, body: dict) -> dict:
        url = f"{self.config.base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            **self.config.extra_headers,
        }

        try:
            response = self._client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as e:
            raise LLMError(f"request timed out after {self.config.timeout}s") from e
        except httpx.HTTPError as e:
            raise LLMError(f"HTTP error: {e}") from e

        if response.status_code >= 400:
            _raise_api_error(response.status_code, response.text)

        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise LLMError(
                "invalid JSON response",
                status_code=response.status_code,
                body=response.text,
            ) from e
