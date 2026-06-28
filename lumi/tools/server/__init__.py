from __future__ import annotations

from lumi.config import ServerToolsConfig
from lumi.tools.server.registry import ServerToolRegistry
from lumi.tools.server.web_search import make_web_search_tool

_SERVER_TOOL_FACTORIES = {
    "WebSearch": make_web_search_tool,
}


def create_server_tool_registry(config: ServerToolsConfig) -> ServerToolRegistry:
    registry = ServerToolRegistry()
    for name in config.enabled:
        registry.register(_SERVER_TOOL_FACTORIES[name](config))
    return registry
