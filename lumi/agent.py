from __future__ import annotations

import time

from lumi.config import AgentConfig, resolve_adapter
from lumi.events import EventBus, measure_ms
from lumi.llm.base import LLM, LLMResponse
from lumi.messages import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolMessage,
    UserMessage,
    truncate_messages,
)
from lumi.tools.registry import ToolRegistry
from lumi.tools.server.registry import ServerToolRegistry


class AgentError(Exception):
    pass


class MaxStepsExceeded(AgentError):
    def __init__(self, max_steps: int, messages: list[Message]):
        self.max_steps = max_steps
        self.messages = messages
        super().__init__(f"max steps ({max_steps}) exceeded")


class Agent:
    def __init__(
        self,
        llm: LLM,
        tools: ToolRegistry,
        config: AgentConfig,
        system_prompt: str,
        server_tools: ServerToolRegistry | None = None,
        events: EventBus | None = None,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.config = config
        self.events = events or EventBus()
        self._messages: list[Message] = [SystemMessage(content=system_prompt)]
        self._tool_schemas = tools.schemas()
        self._server_tool_schemas = server_tools.schemas() if server_tools else []
        self._adapter = resolve_adapter(llm.config.provider)

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    def reset(self) -> None:
        system = self._messages[0] if self._messages else None
        self._messages = [system] if isinstance(system, SystemMessage) else []

    def run(self, user_input: str) -> str:
        self.reset()
        return self.chat(user_input)

    def chat(self, user_input: str) -> str:
        self.events.emit("agent_start", user_input=user_input)
        self._messages.append(UserMessage(content=user_input))

        result = ""
        steps = 0
        error: Exception | None = None

        try:
            for step in range(self.config.max_steps):
                steps = step + 1
                self.events.emit(
                    "step_start", step=step, max_steps=self.config.max_steps
                )

                context = truncate_messages(
                    self._messages, self.config.context_window
                )
                tool_schemas = self._all_tool_schemas()

                self.events.emit(
                    "llm_request", messages=context, tools=tool_schemas
                )
                response = self.llm.chat(context, tools=tool_schemas)
                self.events.emit("llm_response", response=response)

                self._append_assistant_response(response)

                if not response.tool_calls:
                    result = response.content or ""
                    self.events.emit(
                        "step_complete", step=step, final=True
                    )
                    break

                for call in response.tool_calls:
                    self.events.emit(
                        "tool_start", name=call.name, arguments=call.arguments
                    )
                    start = time.perf_counter()
                    tool_result = self.tools.execute(call.name, call.arguments)
                    duration_ms = measure_ms(start)
                    self.events.emit(
                        "tool_end",
                        name=call.name,
                        result=tool_result,
                        duration_ms=duration_ms,
                    )
                    self._messages.append(
                        ToolMessage(tool_call_id=call.id, content=tool_result)
                    )

                self.events.emit("step_complete", step=step, final=False)
            else:
                raise MaxStepsExceeded(self.config.max_steps, self._messages)

        except Exception as e:
            error = e
            self.events.emit("error", error=e)
            raise
        finally:
            self.events.emit("agent_end", result=result, steps=steps, error=error)

        return result

    def _all_tool_schemas(self) -> list[dict]:
        if self._adapter == "anthropic":
            return self.tools.schemas_anthropic() + self._server_tool_schemas
        return self._tool_schemas

    def _append_assistant_response(self, response: LLMResponse) -> None:
        for blocks in response.prior_assistant_blocks:
            self._messages.append(AssistantMessage(raw_blocks=blocks))
        self._messages.append(
            AssistantMessage(
                content=response.content,
                tool_calls=response.tool_calls,
                raw_blocks=response.raw_blocks,
            )
        )
