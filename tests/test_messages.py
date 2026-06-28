from __future__ import annotations

from lumi.messages import (
    AssistantMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
    to_api_format,
    truncate_messages,
)


def test_to_api_format() -> None:
    messages = [
        SystemMessage(content="sys"),
        UserMessage(content="hello"),
        AssistantMessage(
            content=None,
            tool_calls=[ToolCall(id="1", name="Read", arguments={"path": "a"})],
        ),
        ToolMessage(tool_call_id="1", content="file content"),
    ]
    api = to_api_format(messages)
    assert api[0]["role"] == "system"
    assert api[2]["tool_calls"][0]["function"]["name"] == "Read"


def test_truncate_keeps_system() -> None:
    messages = [SystemMessage(content="sys")]
    messages.extend(UserMessage(content=str(i)) for i in range(10))
    truncated = truncate_messages(messages, max_count=5)
    assert isinstance(truncated[0], SystemMessage)
    assert len(truncated) == 5


def test_truncate_preserves_tool_pairs() -> None:
    messages = [
        SystemMessage(content="sys"),
        UserMessage(content="first"),
        AssistantMessage(
            content=None,
            tool_calls=[ToolCall(id="1", name="Read", arguments={"path": "a"})],
        ),
        ToolMessage(tool_call_id="1", content="a"),
        UserMessage(content="second"),
        AssistantMessage(content="done"),
    ]
    truncated = truncate_messages(messages, max_count=4)
    roles = [type(m).__name__ for m in truncated]
    assert roles[0] == "SystemMessage"
    assert "ToolMessage" not in roles or "AssistantMessage" in roles[: roles.index("ToolMessage") + 1]
    assert not isinstance(truncated[1], ToolMessage)


def test_truncate_expands_to_complete_tool_turn() -> None:
    messages = [
        SystemMessage(content="sys"),
        UserMessage(content="old"),
        AssistantMessage(content="old reply"),
        UserMessage(content="new"),
        AssistantMessage(
            content=None,
            tool_calls=[ToolCall(id="2", name="Read", arguments={"path": "b"})],
        ),
        ToolMessage(tool_call_id="2", content="b"),
        UserMessage(content="latest"),
    ]
    truncated = truncate_messages(messages, max_count=4)
    assert isinstance(truncated[0], SystemMessage)
    assert not isinstance(truncated[1], ToolMessage)
    assert truncated[-1].content == "latest"


def test_truncate_keeps_search_turn_with_raw_blocks() -> None:
    search_blocks = [
        {"type": "server_tool_use", "id": "s1", "name": "web_search"},
        {
            "type": "web_search_tool_result",
            "tool_use_id": "s1",
            "content": [{"title": "A"}],
        },
    ]
    messages = [
        SystemMessage(content="sys"),
        UserMessage(content="old question"),
        AssistantMessage(content="old answer"),
        UserMessage(content="search topic"),
        AssistantMessage(raw_blocks=search_blocks),
        AssistantMessage(
            content="here are results",
            raw_blocks=[{"type": "text", "text": "here are results"}],
        ),
        UserMessage(content="follow up"),
    ]
    truncated = truncate_messages(messages, max_count=5)

    assert isinstance(truncated[0], SystemMessage)
    assert not isinstance(truncated[1], ToolMessage)
    assert truncated[-1].content == "follow up"
    raw_block_turn = [
        message for message in truncated if getattr(message, "raw_blocks", None) == search_blocks
    ]
    assert len(raw_block_turn) == 1


