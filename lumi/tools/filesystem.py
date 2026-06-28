from __future__ import annotations

from pathlib import Path

from lumi.tools.registry import Tool
from lumi.tools.workspace import resolve_path

MAX_FILE_SIZE = 100 * 1024


def make_read_tool(workspace: Path) -> Tool:
    def read(path: str) -> str:
        file_path, error = resolve_path(workspace, path)
        if error:
            return error
        assert file_path is not None

        if not file_path.exists():
            return f"Error: file not found: {path}"
        if file_path.is_dir():
            return f"Error: {path} is a directory"
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE:
            return f"Error: file too large ({size} bytes, max {MAX_FILE_SIZE})"
        return file_path.read_text(encoding="utf-8", errors="replace")

    return Tool(
        name="Read",
        description="Read the contents of a file at the given path (relative to workspace).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
            },
            "required": ["path"],
        },
        handler=read,
    )


def make_write_tool(workspace: Path) -> Tool:
    def write(path: str, content: str) -> str:
        file_path, error = resolve_path(workspace, path)
        if error:
            return error
        assert file_path is not None

        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {path}"

    return Tool(
        name="Write",
        description=(
            "Write content to a file at the given path (relative to workspace). "
            "Creates parent directories if needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
        handler=write,
    )
