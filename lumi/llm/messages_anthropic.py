from __future__ import annotations

from lumi.config import LLMConfig
from lumi.llm.base import LLMResponse, TokenUsage
from lumi.messages import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)


def split_system_messages(messages: list[Message]) -> tuple[str, list[Message]]:
    system_parts = [m.content for m in messages if isinstance(m, SystemMessage)]
    non_system = [m for m in messages if not isinstance(m, SystemMessage)]
    return "\n\n".join(part for part in system_parts if part), non_system


def to_anthropic_messages(messages: list[Message]) -> list[dict]:
    _, non_system = split_system_messages(messages)
    result: list[dict] = []
    index = 0

    while index < len(non_system):
        msg = non_system[index]
        if isinstance(msg, UserMessage):
            result.append(
                {
                    "role": "user",
                    "content": [{"type": "text", "text": msg.content}],
                }
            )
            index += 1
            continue

        if isinstance(msg, AssistantMessage):
            blocks = _assistant_to_blocks(msg)
            result.append({"role": "assistant", "content": blocks})
            index += 1
            continue

        if isinstance(msg, ToolMessage):
            blocks: list[dict] = []
            while index < len(non_system) and isinstance(non_system[index], ToolMessage):
                tool_msg = non_system[index]
                blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_msg.tool_call_id,
                        "content": tool_msg.content,
                    }
                )
                index += 1
            result.append({"role": "user", "content": blocks})
            continue

        index += 1

    return result


def build_anthropic_request_body(
    config: LLMConfig,
    anthropic_messages: list[dict],
    tools: list[dict] | None,
    *,
    system: str = "",
) -> dict:
    body: dict = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "messages": anthropic_messages,
        "temperature": config.temperature,
    }
    if system:
        body["system"] = system
    if tools:
        body["tools"] = tools
    return body


def build_anthropic_request(
    messages: list[Message],
    config: LLMConfig,
    tools: list[dict] | None,
) -> dict:
    system, _ = split_system_messages(messages)
    return build_anthropic_request_body(
        config,
        to_anthropic_messages(messages),
        tools,
        system=system,
    )


def extract_text_blocks(content: list[dict]) -> str:
    parts = [block["text"] for block in content if block.get("type") == "text" and block.get("text")]
    return "\n".join(parts).strip()


def extract_client_tool_calls(content: list[dict]) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []
    for block in content:
        if block.get("type") != "tool_use":
            continue
        tool_calls.append(
            ToolCall(
                id=block["id"],
                name=block["name"],
                arguments=block.get("input") or {},
            )
        )
    return tool_calls


def has_server_tool_activity(content: list[dict]) -> bool:
    server_types = {"server_tool_use", "web_search_tool_result"}
    return any(block.get("type") in server_types for block in content)


def count_server_tool_uses(content: list[dict]) -> int:
    return sum(1 for block in content if block.get("type") == "server_tool_use")


def count_search_results(content: list[dict]) -> int:
    total = 0
    for block in content:
        if block.get("type") != "web_search_tool_result":
            continue
        result_content = block.get("content")
        if isinstance(result_content, list):
            total += len(result_content)
        elif result_content:
            total += 1
    return total


def parse_anthropic_response(data: dict) -> LLMResponse:
    content = data.get("content") or []
    usage = None
    if "usage" in data:
        raw_usage = data["usage"]
        usage = TokenUsage(
            prompt_tokens=raw_usage.get("input_tokens", 0),
            completion_tokens=raw_usage.get("output_tokens", 0),
            total_tokens=raw_usage.get("input_tokens", 0) + raw_usage.get("output_tokens", 0),
        )

    return LLMResponse(
        content=extract_text_blocks(content) or None,
        tool_calls=extract_client_tool_calls(content),
        usage=usage,
        raw=data,
        server_tool_uses=count_server_tool_uses(content),
        raw_blocks=list(content) if content else None,
    )


def _assistant_to_blocks(message: AssistantMessage) -> list[dict]:
    if message.raw_blocks is not None:
        return list(message.raw_blocks)

    blocks: list[dict] = []
    if message.content:
        blocks.append({"type": "text", "text": message.content})
    for tool_call in message.tool_calls:
        blocks.append(
            {
                "type": "tool_use",
                "id": tool_call.id,
                "name": tool_call.name,
                "input": tool_call.arguments,
            }
        )
    return blocks or [{"type": "text", "text": ""}]
