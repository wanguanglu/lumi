from __future__ import annotations

from lumi.config import ToolsConfig
from lumi.tools.filesystem import read_file_tool, write_file_tool
from lumi.tools.registry import ToolRegistry
from lumi.tools.shell import make_run_shell_tool

BUILTINS = {
    "read_file": read_file_tool,
    "write_file": write_file_tool,
}


def create_tool_registry(config: ToolsConfig) -> ToolRegistry:
    registry = ToolRegistry()
    builtins = {**BUILTINS, "run_shell": make_run_shell_tool(config)}

    for name in config.enabled:
        registry.register(builtins[name])

    return registry
