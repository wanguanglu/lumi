from __future__ import annotations

from lumi.messages import (
    AssistantMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from lumi.llm.messages_anthropic import (
    build_anthropic_request,
    extract_client_tool_calls,
    extract_text_blocks,
    has_server_tool_activity,
    to_anthropic_messages,
)


def test_to_anthropic_messages_user_and_tool_result() -> None:
    messages = [
        SystemMessage(content="sys"),
        UserMessage(content="hello"),
        AssistantMessage(
            content=None,
            tool_calls=[ToolCall(id="1", name="Read", arguments={"path": "a.txt"})],
        ),
        ToolMessage(tool_call_id="1", content="file"),
    ]
    api_messages = to_anthropic_messages(messages)
    assert api_messages[0]["role"] == "user"
    assert api_messages[1]["role"] == "assistant"
    assert api_messages[1]["content"][0]["type"] == "tool_use"
    assert api_messages[2]["role"] == "user"
    assert api_messages[2]["content"][0]["type"] == "tool_result"


def test_build_anthropic_request_includes_system_and_tools() -> None:
    from lumi.config import LLMConfig

    config = LLMConfig(
        provider="deepseek-anthropic",
        base_url="https://api.deepseek.com/anthropic",
        api_key="key",
        model="deepseek-v4-pro",
    )
    messages = [SystemMessage(content="sys"), UserMessage(content="hi")]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}]
    body = build_anthropic_request(messages, config, tools)
    assert body["system"] == "sys"
    assert body["tools"] == tools
    assert body["messages"][0]["content"][0]["text"] == "hi"


def test_extract_client_tool_calls() -> None:
    content = [
        {"type": "tool_use", "id": "1", "name": "Write", "input": {"path": "a", "content": "x"}},
    ]
    calls = extract_client_tool_calls(content)
    assert len(calls) == 1
    assert calls[0].name == "Write"


def test_extract_text_and_server_activity() -> None:
    content = [
        {"type": "server_tool_use", "id": "s1", "name": "web_search"},
        {"type": "web_search_tool_result", "tool_use_id": "s1", "content": [{"title": "A"}]},
        {"type": "text", "text": "answer"},
    ]
    assert has_server_tool_activity(content)
    assert extract_text_blocks(content) == "answer"
