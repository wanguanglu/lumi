from __future__ import annotations

from lumi.config import ConfigError, ServerToolsConfig
from lumi.tools.server.registry import ServerToolRegistry
from lumi.tools.server.web_search import make_web_search_tool

BUILTIN_SERVER_TOOLS = frozenset({"WebSearch"})


def create_server_tool_registry(config: ServerToolsConfig) -> ServerToolRegistry:
    registry = ServerToolRegistry()
    factories = {"WebSearch": make_web_search_tool}

    for name in config.enabled:
        if name not in BUILTIN_SERVER_TOOLS:
            raise ConfigError(
                f"unknown server tool: {name} "
                f"(available: {', '.join(sorted(BUILTIN_SERVER_TOOLS))})"
            )
        registry.register(factories[name](config))

    return registry
