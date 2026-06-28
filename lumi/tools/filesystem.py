from __future__ import annotations

from pathlib import Path

from lumi.tools.registry import Tool

MAX_FILE_SIZE = 100 * 1024


def read_file(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return f"Error: file not found: {path}"
    if file_path.is_dir():
        return f"Error: {path} is a directory"
    size = file_path.stat().st_size
    if size > MAX_FILE_SIZE:
        return f"Error: file too large ({size} bytes, max {MAX_FILE_SIZE})"
    return file_path.read_text()


def write_file(path: str, content: str) -> str:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    return f"Successfully wrote {len(content)} bytes to {path}"


read_file_tool = Tool(
    name="read_file",
    description="Read the contents of a file at the given path.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
        },
        "required": ["path"],
    },
    handler=read_file,
)

write_file_tool = Tool(
    name="write_file",
    description="Write content to a file at the given path. Creates parent directories if needed.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    },
    handler=write_file,
)
