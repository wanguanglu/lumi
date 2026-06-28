from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., str]

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        if not isinstance(arguments, dict):
            return f"Error: arguments must be a dict, got {type(arguments).__name__}"
        try:
            return tool.handler(**arguments)
        except TypeError as e:
            return f"Error: invalid arguments for {name}: {e}"
        except Exception as e:
            return f"Error: {e}"

    @property
    def names(self) -> list[str]:
        return list(self._tools.keys())
