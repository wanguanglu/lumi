from __future__ import annotations

from lumi.config import ServerToolsConfig
from lumi.tools.server.registry import ServerTool


def make_web_search_tool(config: ServerToolsConfig) -> ServerTool:
    return ServerTool(
        name="WebSearch",
        api_type=config.web_search_type,
        schema={
            "type": config.web_search_type,
            "name": "web_search",
            "max_uses": config.web_search_max_uses,
        },
    )
