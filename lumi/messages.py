from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class SystemMessage:
    role: Literal["system"] = "system"
    content: str = ""


@dataclass
class UserMessage:
    role: Literal["user"] = "user"
    content: str = ""


@dataclass
class AssistantMessage:
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class ToolMessage:
    role: Literal["tool"] = "tool"
    tool_call_id: str = ""
    content: str = ""


Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage


def to_api_format(messages: list[Message]) -> list[dict]:
    result: list[dict] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, UserMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AssistantMessage):
            entry: dict = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": _arguments_to_json(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            result.append(entry)
        elif isinstance(msg, ToolMessage):
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                }
            )
    return result


def truncate_messages(
    messages: list[Message],
    max_count: int,
    keep_system: bool = True,
) -> list[Message]:
    if max_count <= 0 or len(messages) <= max_count:
        return list(messages)

    system_msgs = [m for m in messages if isinstance(m, SystemMessage)] if keep_system else []
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]

    budget = max_count - len(system_msgs)
    if budget <= 0:
        return system_msgs[:max_count]

    return system_msgs + non_system[-budget:]


def _arguments_to_json(arguments: dict) -> str:
    import json

    return json.dumps(arguments, ensure_ascii=False)
