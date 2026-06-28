from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from lumi.config import ToolsConfig
from lumi.tools.registry import Tool


def _command_allowed(command: str, allowed: list[str]) -> bool:
    if not allowed:
        return True
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
    return parts[0] in allowed


def make_bash_tool(config: ToolsConfig, workspace: Path) -> Tool:
    cwd = workspace.resolve()

    def bash(command: str) -> str:
        if not _command_allowed(command, config.bash_allowed_commands):
            allowed = ", ".join(config.bash_allowed_commands)
            return f"Error: command not allowed (whitelist: {allowed})"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=config.bash_timeout,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {config.bash_timeout}s"

        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout.rstrip())
        if result.stderr:
            output_parts.append(f"stderr:\n{result.stderr.rstrip()}")
        if result.returncode != 0:
            output_parts.append(f"exit code: {result.returncode}")

        return "\n".join(output_parts) if output_parts else "(no output)"

    return Tool(
        name="Bash",
        description="Run a bash command in the workspace and return its stdout/stderr.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command to execute"},
            },
            "required": ["command"],
        },
        handler=bash,
    )
