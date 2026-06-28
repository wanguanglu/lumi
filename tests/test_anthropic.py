from __future__ import annotations

import json

import pytest

from lumi.config import LLMConfig
from lumi.llm.anthropic import AnthropicProvider
from lumi.llm.base import LLMError
from lumi.messages import SystemMessage, UserMessage


@pytest.fixture
def llm_config() -> LLMConfig:
    return LLMConfig(
        provider="deepseek-anthropic",
        base_url="https://api.deepseek.com/anthropic",
        api_key="test-key",
        model="deepseek-v4-pro",
    )


def test_anthropic_text_response(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(
        json={
            "content": [{"type": "text", "text": "Hello!"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 2},
        }
    )
    provider = AnthropicProvider(llm_config)
    try:
        response = provider.chat(
            [SystemMessage(content="sys"), UserMessage(content="hi")],
            tools=[],
        )
    finally:
        provider.close()

    assert response.content == "Hello!"
    assert response.tool_calls == []


def test_anthropic_client_tool_use(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(
        json={
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "Read",
                    "input": {"path": "README.md"},
                }
            ],
            "stop_reason": "tool_use",
        }
    )
    provider = AnthropicProvider(llm_config)
    try:
        response = provider.chat([UserMessage(content="read readme")], tools=[])
    finally:
        provider.close()

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "Read"


def test_anthropic_server_search_inner_loop(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(
        json={
            "content": [
                {"type": "server_tool_use", "id": "srv_1", "name": "web_search"},
                {
                    "type": "web_search_tool_result",
                    "tool_use_id": "srv_1",
                    "content": [{"title": "Result", "url": "https://example.com"}],
                },
            ],
            "stop_reason": "tool_use",
        }
    )
    httpx_mock.add_response(
        json={
            "content": [{"type": "text", "text": "Based on search, here is the answer."}],
            "stop_reason": "end_turn",
        }
    )

    provider = AnthropicProvider(llm_config)
    try:
        response = provider.chat([UserMessage(content="latest news")], tools=[])
    finally:
        provider.close()

    assert response.content == "Based on search, here is the answer."
    assert response.server_tool_uses == 1
    assert len(response.prior_assistant_blocks) == 1
    assert response.prior_assistant_blocks[0][0]["type"] == "server_tool_use"
    assert response.raw_blocks == [{"type": "text", "text": "Based on search, here is the answer."}]
    assert len(httpx_mock.get_requests()) == 2


def test_anthropic_api_error(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(
        status_code=400,
        text=json.dumps({"error": {"message": "Invalid model"}}),
    )
    provider = AnthropicProvider(llm_config)
    try:
        with pytest.raises(LLMError, match="Invalid model"):
            provider.chat([UserMessage(content="hi")])
    finally:
        provider.close()


def test_anthropic_uses_x_api_key_header(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(
        json={"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}
    )
    provider = AnthropicProvider(llm_config)
    try:
        provider.chat([UserMessage(content="hi")])
    finally:
        provider.close()

    request = httpx_mock.get_requests()[0]
    assert request.headers["x-api-key"] == "test-key"
