from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ServerTool:
    name: str
    api_type: str
    schema: dict


class ServerToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ServerTool] = {}

    def register(self, tool: ServerTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ServerTool | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict]:
        return [tool.schema for tool in self._tools.values()]

    @property
    def names(self) -> list[str]:
        return list(self._tools.keys())
