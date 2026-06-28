from __future__ import annotations

import pytest

from lumi.config import ConfigError, ServerToolsConfig
from lumi.tools.server import create_server_tool_registry


def test_web_search_schema() -> None:
    registry = create_server_tool_registry(
        ServerToolsConfig(enabled=["WebSearch"], web_search_max_uses=3)
    )
    schemas = registry.schemas()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "web_search_20260209"
    assert schemas[0]["name"] == "web_search"
    assert schemas[0]["max_uses"] == 3


def test_unknown_server_tool() -> None:
    with pytest.raises(ConfigError, match="unknown server tool"):
        create_server_tool_registry(ServerToolsConfig(enabled=["Unknown"]))
