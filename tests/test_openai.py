from __future__ import annotations

import json

import pytest

from lumi.config import LLMConfig
from lumi.llm.base import LLMAuthError, LLMError, LLMRateLimitError
from lumi.llm.openai import OpenAIProvider, _extract_error_message
from lumi.messages import SystemMessage, UserMessage


@pytest.fixture
def llm_config() -> LLMConfig:
    return LLMConfig(
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
        api_key="test-key",
        model="deepseek-chat",
    )


def test_extract_error_message() -> None:
    body = json.dumps({"error": {"message": "Invalid model"}})
    assert _extract_error_message(body) == "Invalid model"


def test_chat_text_response(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(
        json={
            "choices": [{"message": {"role": "assistant", "content": "Hello!"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }
    )

    provider = OpenAIProvider(llm_config)
    try:
        response = provider.chat(
            [SystemMessage(content="sys"), UserMessage(content="hi")]
        )
    finally:
        provider.close()

    assert response.content == "Hello!"
    assert response.tool_calls == []
    assert response.usage is not None
    assert response.usage.total_tokens == 3


def test_chat_tool_calls(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(
        json={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "Read",
                                    "arguments": '{"path": "README.md"}',
                                },
                            }
                        ],
                    }
                }
            ]
        }
    )

    provider = OpenAIProvider(llm_config)
    try:
        response = provider.chat([UserMessage(content="read readme")])
    finally:
        provider.close()

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "Read"
    assert response.tool_calls[0].arguments == {"path": "README.md"}


@pytest.mark.parametrize(
    ("status_code", "body", "error_type", "message"),
    [
        (401, '{"error":{"message":"Invalid API key"}}', LLMAuthError, "Invalid API key"),
        (429, '{"error":{"message":"Rate limit reached"}}', LLMRateLimitError, "Rate limit reached"),
        (400, '{"error":{"message":"Invalid model"}}', LLMError, "Invalid model"),
    ],
)
def test_chat_api_errors(
    httpx_mock,
    llm_config: LLMConfig,
    status_code: int,
    body: str,
    error_type: type[LLMError],
    message: str,
) -> None:
    httpx_mock.add_response(status_code=status_code, text=body)

    provider = OpenAIProvider(llm_config)
    try:
        with pytest.raises(error_type) as exc_info:
            provider.chat([UserMessage(content="hi")])
        assert str(exc_info.value) == message
        assert exc_info.value.status_code == status_code
        assert exc_info.value.body == body
    finally:
        provider.close()


def test_chat_invalid_json_response(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(status_code=200, text="not-json")

    provider = OpenAIProvider(llm_config)
    try:
        with pytest.raises(LLMError, match="invalid JSON response"):
            provider.chat([UserMessage(content="hi")])
    finally:
        provider.close()


def test_chat_invalid_response_shape(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(json={"choices": []})

    provider = OpenAIProvider(llm_config)
    try:
        with pytest.raises(LLMError, match="invalid API response"):
            provider.chat([UserMessage(content="hi")])
    finally:
        provider.close()


def test_provider_context_manager(httpx_mock, llm_config: LLMConfig) -> None:
    httpx_mock.add_response(
        json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
    )

    with OpenAIProvider(llm_config) as provider:
        response = provider.chat([UserMessage(content="hi")])

    assert response.content == "ok"
