from __future__ import annotations

from dataclasses import dataclass

import pytest

from lumi.agent import Agent, MaxStepsExceeded
from lumi.config import AgentConfig
from lumi.events import EventBus
from lumi.llm.base import LLMResponse
from lumi.messages import ToolCall
from lumi.tools import create_tool_registry
from lumi.config import ToolsConfig


@dataclass
class MockLLM:
    responses: list[LLMResponse]

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

