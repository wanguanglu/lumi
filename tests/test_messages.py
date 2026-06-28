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
            tool_calls=[ToolCall(id="1", name="read_file", arguments={"path": "a"})],
        ),
        ToolMessage(tool_call_id="1", content="file content"),
    ]
    api = to_api_format(messages)
    assert api[0]["role"] == "system"
    assert api[2]["tool_calls"][0]["function"]["name"] == "read_file"


def test_truncate_keeps_system() -> None:
    messages = [SystemMessage(content="sys")]
    messages.extend(UserMessage(content=str(i)) for i in range(10))
    truncated = truncate_messages(messages, max_count=5)
    assert isinstance(truncated[0], SystemMessage)
    assert len(truncated) == 5
