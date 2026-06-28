from __future__ import annotations

from pathlib import Path

from lumi.config import ToolsConfig
from lumi.tools import create_tool_registry
from lumi.tools.filesystem import read_file, write_file


def test_read_file(tmp_path: Path) -> None:
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    assert read_file(str(f)) == "hello world"


def test_read_file_not_found() -> None:
    assert "Error: file not found" in read_file("/nonexistent/path.txt")


def test_write_file(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "out.txt"
    result = write_file(str(path), "content")
    assert "Successfully wrote" in result
    assert path.read_text() == "content"


def test_shell_whitelist() -> None:
    config = ToolsConfig(
        enabled=["run_shell"],
        shell_timeout=5,
        shell_allowed_commands=["echo"],
    )
    registry = create_tool_registry(config)
    result = registry.execute("run_shell", {"command": "echo hi"})
    assert "hi" in result

    blocked = registry.execute("run_shell", {"command": "rm -rf /"})
    assert "not allowed" in blocked


def test_unknown_tool() -> None:
    registry = create_tool_registry(ToolsConfig(enabled=["read_file"]))
    result = registry.execute("missing", {})
    assert "unknown tool" in result
