from __future__ import annotations

from pathlib import Path

import pytest

from lumi.config import ToolsConfig
from lumi.tools import create_tool_registry
from lumi.tools.workspace import resolve_path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def test_resolve_path_relative(workspace: Path) -> None:
    target, error = resolve_path(workspace, "src/main.py")
    assert error is None
    assert target == (workspace / "src/main.py").resolve()


def test_resolve_path_blocks_traversal(workspace: Path) -> None:
    _, error = resolve_path(workspace, "../outside.txt")
    assert error is not None
    assert "outside workspace" in error


def test_resolve_path_blocks_absolute_outside(workspace: Path) -> None:
    _, error = resolve_path(workspace, "/etc/passwd")
    assert error is not None
    assert "outside workspace" in error


def test_read_tool(workspace: Path) -> None:
    file_path = workspace / "hello.txt"
    file_path.write_text("hello world")
    registry = create_tool_registry(ToolsConfig(enabled=["Read"], workspace=str(workspace)))
    assert registry.execute("Read", {"path": "hello.txt"}) == "hello world"


def test_read_tool_not_found(workspace: Path) -> None:
    registry = create_tool_registry(ToolsConfig(enabled=["Read"], workspace=str(workspace)))
    result = registry.execute("Read", {"path": "missing.txt"})
    assert "Error: file not found" in result


def test_read_tool_blocks_traversal(workspace: Path) -> None:
    outside = workspace.parent / "outside.txt"
    outside.write_text("secret")
    registry = create_tool_registry(ToolsConfig(enabled=["Read"], workspace=str(workspace)))
    result = registry.execute("Read", {"path": "../outside.txt"})
    assert "outside workspace" in result


def test_read_tool_too_large(workspace: Path) -> None:
    large = workspace / "large.txt"
    large.write_text("x" * (100 * 1024 + 1))
    registry = create_tool_registry(ToolsConfig(enabled=["Read"], workspace=str(workspace)))
    result = registry.execute("Read", {"path": "large.txt"})
    assert "too large" in result


def test_write_tool(workspace: Path) -> None:
    registry = create_tool_registry(ToolsConfig(enabled=["Write"], workspace=str(workspace)))
    result = registry.execute("Write", {"path": "sub/out.txt", "content": "content"})
    assert "Successfully wrote" in result
    assert (workspace / "sub/out.txt").read_text() == "content"


def test_write_tool_blocks_traversal(workspace: Path) -> None:
    registry = create_tool_registry(ToolsConfig(enabled=["Write"], workspace=str(workspace)))
    result = registry.execute(
        "Write", {"path": "../escape.txt", "content": "bad"}
    )
    assert "outside workspace" in result


def test_bash_runs_in_workspace(workspace: Path) -> None:
    (workspace / "marker.txt").write_text("ok")
    registry = create_tool_registry(
        ToolsConfig(
            enabled=["Bash"],
            workspace=str(workspace),
            bash_allowed_commands=["ls"],
        )
    )
    result = registry.execute("Bash", {"command": "ls marker.txt"})
    assert "marker.txt" in result


def test_bash_whitelist(workspace: Path) -> None:
    registry = create_tool_registry(
        ToolsConfig(
            enabled=["Bash"],
            workspace=str(workspace),
            bash_timeout=5,
            bash_allowed_commands=["echo"],
        )
    )
    result = registry.execute("Bash", {"command": "echo hi"})
    assert "hi" in result

    blocked = registry.execute("Bash", {"command": "rm -rf /"})
    assert "not allowed" in blocked


def test_unknown_tool(workspace: Path) -> None:
    registry = create_tool_registry(ToolsConfig(enabled=["Read"], workspace=str(workspace)))
    result = registry.execute("missing", {})
    assert "unknown tool" in result


def test_invalid_arguments_type(workspace: Path) -> None:
    registry = create_tool_registry(ToolsConfig(enabled=["Read"], workspace=str(workspace)))
    result = registry.execute("Read", "not-a-dict")  # type: ignore[arg-type]
    assert "arguments must be a dict" in result
