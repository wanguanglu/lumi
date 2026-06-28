from __future__ import annotations

from pathlib import Path

from lumi.config import ToolsConfig
from lumi.tools.bash import make_bash_tool
from lumi.tools.filesystem import make_read_tool, make_write_tool
from lumi.tools.registry import ToolRegistry


def create_tool_registry(config: ToolsConfig) -> ToolRegistry:
    workspace = Path(config.workspace).resolve()
    registry = ToolRegistry()
    builtins = {
        "Read": make_read_tool(workspace),
        "Write": make_write_tool(workspace),
        "Bash": make_bash_tool(config, workspace),
    }

    for name in config.enabled:
        registry.register(builtins[name])

    return registry
