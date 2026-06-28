from __future__ import annotations

import json

import pytest

from lumi.config import LLMConfig
from lumi.events import EventBus
from lumi.llm.anthropic import AnthropicProvider, MAX_INNER_STEPS
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


def _search_only_response() -> dict:
    return {
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


def test_anthropic_max_inner_steps_exceeded(httpx_mock, llm_config: LLMConfig) -> None:
    for _ in range(MAX_INNER_STEPS):
        httpx_mock.add_response(json=_search_only_response())

    provider = AnthropicProvider(llm_config)
    try:
        with pytest.raises(LLMError, match="max inner steps"):
            provider.chat([UserMessage(content="keep searching")])
    finally:
        provider.close()

    assert len(httpx_mock.get_requests()) == MAX_INNER_STEPS


def test_anthropic_search_then_client_tool(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(json=_search_only_response())
    httpx_mock.add_response(
        json={
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "Write",
                    "input": {"path": "notes.md", "content": "summary"},
                }
            ],
            "stop_reason": "tool_use",
        }
    )

    provider = AnthropicProvider(llm_config)
    try:
        response = provider.chat([UserMessage(content="search and write notes")], tools=[])
    finally:
        provider.close()

    assert len(response.prior_assistant_blocks) == 1
    assert response.prior_assistant_blocks[0][0]["type"] == "server_tool_use"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "Write"
    assert len(httpx_mock.get_requests()) == 2


def test_anthropic_server_tool_end_event_uses_block_name(
    httpx_mock, llm_config: LLMConfig
) -> None:
    httpx_mock.add_response(json=_search_only_response())
    httpx_mock.add_response(
        json={
            "content": [{"type": "text", "text": "done"}],
            "stop_reason": "end_turn",
        }
    )

    events = EventBus()
    ends: list[dict] = []
    events.on("server_tool_end", lambda **kwargs: ends.append(kwargs))

    provider = AnthropicProvider(llm_config, events=events)
    try:
        provider.chat([UserMessage(content="news")])
    finally:
        provider.close()

    assert len(ends) == 1
    assert ends[0]["name"] == "web_search"
    assert ends[0]["results_count"] == 1

