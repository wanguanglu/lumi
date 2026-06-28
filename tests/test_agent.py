from __future__ import annotations

from dataclasses import dataclass

import pytest

from lumi.agent import Agent, MaxStepsExceeded
from lumi.config import AgentConfig
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
        tools=create_tool_registry(ToolsConfig(enabled=["read_file"])),
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
                    ToolCall(id="1", name="read_file", arguments={"path": "x.txt"})
                ],
                usage=None,
                raw={},
            ),
            LLMResponse(content="Done reading.", tool_calls=[], usage=None, raw={}),
        ]
    )
    agent = Agent(
        llm=llm,
        tools=create_tool_registry(ToolsConfig(enabled=["read_file"])),
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
                    ToolCall(id="1", name="read_file", arguments={"path": "a"})
                ],
                usage=None,
                raw={},
            )
        ]
        * 3
    )
    agent = Agent(
        llm=llm,
        tools=create_tool_registry(ToolsConfig(enabled=["read_file"])),
        config=AgentConfig(max_steps=2),
        system_prompt="test",
    )
    with pytest.raises(MaxStepsExceeded):
        agent.run("loop forever")
