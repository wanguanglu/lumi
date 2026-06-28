from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from lumi.agent import Agent, MaxStepsExceeded
from lumi.config import AgentConfig
from lumi.events import EventBus
from lumi.llm.base import LLMResponse
from lumi.messages import AssistantMessage, ToolCall
from lumi.tools import create_tool_registry
from lumi.config import ToolsConfig


@dataclass
class MockLLMConfig:
    provider: str = "deepseek"


@dataclass
class MockLLM:
    responses: list[LLMResponse]
    config: MockLLMConfig = field(default_factory=MockLLMConfig)

    def __post_init__(self) -> None:
        self._call = 0

    def chat(self, messages, tools=None) -> LLMResponse:
        response = self.responses[self._call]
        self._call += 1
        return response


def test_agent_completes_without_tools() -> None:
    llm = MockLLM([LLMResponse(content="Hello!", tool_calls=[], usage=None, raw={})])
    agent = Agent(
        llm=llm,
        tools=create_tool_registry(ToolsConfig(enabled=["Read"])),
        config=AgentConfig(max_steps=5),
        system_prompt="test",
    )
    result = agent.run("hi")
    assert result == "Hello!"


def test_agent_tool_loop() -> None:
    llm = MockLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="1", name="Read", arguments={"path": "x.txt"})
                ],
                usage=None,
                raw={},
            ),
            LLMResponse(content="Done reading.", tool_calls=[], usage=None, raw={}),
        ]
    )
    agent = Agent(
        llm=llm,
        tools=create_tool_registry(ToolsConfig(enabled=["Read"])),
        config=AgentConfig(max_steps=5),
        system_prompt="test",
    )
    result = agent.run("read x.txt")
    assert result == "Done reading."
    assert llm._call == 2


def test_agent_max_steps() -> None:
    llm = MockLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="1", name="Read", arguments={"path": "a"})
                ],
                usage=None,
                raw={},
            )
        ]
        * 3
    )
    agent = Agent(
        llm=llm,
        tools=create_tool_registry(ToolsConfig(enabled=["Read"])),
        config=AgentConfig(max_steps=2),
        system_prompt="test",
    )
    with pytest.raises(MaxStepsExceeded):
        agent.run("loop forever")


def test_agent_end_emitted_on_error() -> None:
    llm = MockLLM(
        [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="1", name="Read", arguments={"path": "a"})
                ],
                usage=None,
                raw={},
            )
        ]
    )
    events = EventBus()
    agent_ends: list[dict] = []
    events.on("agent_end", lambda **kwargs: agent_ends.append(kwargs))

    agent = Agent(
        llm=llm,
        tools=create_tool_registry(ToolsConfig(enabled=["Read"])),
        config=AgentConfig(max_steps=1),
        system_prompt="test",
        events=events,
    )

    with pytest.raises(MaxStepsExceeded):
        agent.run("loop forever")

    assert len(agent_ends) == 1
    assert agent_ends[0]["error"] is not None
    assert agent_ends[0]["steps"] == 1


def test_agent_end_emitted_on_success() -> None:
    llm = MockLLM([LLMResponse(content="Hello!", tool_calls=[], usage=None, raw={})])
    events = EventBus()
    agent_ends: list[dict] = []
    events.on("agent_end", lambda **kwargs: agent_ends.append(kwargs))

    agent = Agent(
        llm=llm,
        tools=create_tool_registry(ToolsConfig(enabled=["Read"])),
        config=AgentConfig(max_steps=5),
        system_prompt="test",
        events=events,
    )
    agent.run("hi")

    assert len(agent_ends) == 1
    assert agent_ends[0]["error"] is None
    assert agent_ends[0]["result"] == "Hello!"


def test_agent_stores_raw_blocks() -> None:
    search_blocks = [
        {"type": "server_tool_use", "id": "s1", "name": "web_search"},
        {
            "type": "web_search_tool_result",
            "tool_use_id": "s1",
            "content": [{"title": "Result"}],
        },
    ]
    llm = MockLLM(
        [
            LLMResponse(
                content="Found it.",
                tool_calls=[],
                usage=None,
                raw={},
                prior_assistant_blocks=[search_blocks],
                raw_blocks=[{"type": "text", "text": "Found it."}],
            )
        ]
    )
    agent = Agent(
        llm=llm,
        tools=create_tool_registry(ToolsConfig(enabled=["Read"])),
        config=AgentConfig(max_steps=5),
        system_prompt="test",
    )
    agent.run("search something")

    stored = agent.messages
    assert isinstance(stored[2], AssistantMessage)
    assert stored[2].raw_blocks == search_blocks
    assert isinstance(stored[3], AssistantMessage)
    assert stored[3].content == "Found it."
    assert stored[3].raw_blocks == [{"type": "text", "text": "Found it."}]


def test_agent_multiturn_preserves_raw_blocks_for_anthropic() -> None:
    from lumi.llm.messages_anthropic import to_anthropic_messages

    search_blocks = [
        {"type": "server_tool_use", "id": "s1", "name": "web_search"},
        {
            "type": "web_search_tool_result",
            "tool_use_id": "s1",
            "content": [{"title": "Link A", "url": "https://a.example"}],
        },
    ]
    captured: list[list] = []

    @dataclass
    class CapturingMockLLM:
        config: MockLLMConfig = field(default_factory=lambda: MockLLMConfig(provider="deepseek-anthropic"))
        _call: int = 0

        def chat(self, messages, tools=None) -> LLMResponse:
            captured.append(messages)
            if self._call == 0:
                self._call += 1
                return LLMResponse(
                    content="First link is Link A.",
                    tool_calls=[],
                    usage=None,
                    raw={},
                    prior_assistant_blocks=[search_blocks],
                    raw_blocks=[{"type": "text", "text": "First link is Link A."}],
                )
            return LLMResponse(content="Link A is about topic X.", tool_calls=[], usage=None, raw={})

    agent = Agent(
        llm=CapturingMockLLM(),
        tools=create_tool_registry(ToolsConfig(enabled=["Read"])),
        config=AgentConfig(max_steps=5),
        system_prompt="test",
    )
    agent.chat("search topic")
    agent.chat("tell me more about the first link")

    second_request = captured[1]
    api_messages = to_anthropic_messages(second_request)
    assert api_messages[1]["content"] == search_blocks
    assert api_messages[2]["content"][0]["text"] == "First link is Link A."
    assert api_messages[3]["content"][0]["text"] == "tell me more about the first link"


