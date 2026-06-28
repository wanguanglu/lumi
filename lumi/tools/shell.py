from __future__ import annotations

import shlex
import subprocess

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


def make_run_shell_tool(config: ToolsConfig) -> Tool:
    def run_shell(command: str) -> str:
        if not _command_allowed(command, config.shell_allowed_commands):
            allowed = ", ".join(config.shell_allowed_commands)
            return f"Error: command not allowed (whitelist: {allowed})"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=config.shell_timeout,
            )
        except subprocess.TimeoutExpired:
            return f"Error: command timed out after {config.shell_timeout}s"

        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout.rstrip())
        if result.stderr:
            output_parts.append(f"stderr:\n{result.stderr.rstrip()}")
        if result.returncode != 0:
            output_parts.append(f"exit code: {result.returncode}")

        return "\n".join(output_parts) if output_parts else "(no output)"

    return Tool(
        name="run_shell",
        description="Execute a shell command and return its stdout/stderr.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
            },
            "required": ["command"],
        },
        handler=run_shell,
    )
