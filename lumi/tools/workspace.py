from __future__ import annotations

from pathlib import Path


def resolve_path(workspace: Path, path: str) -> tuple[Path | None, str | None]:
    root = workspace.resolve()
    candidate = Path(path)
    target = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()

    try:
        if not target.is_relative_to(root):
            return None, f"Error: path outside workspace: {path}"
    except ValueError:
        return None, f"Error: path outside workspace: {path}"

    return target, None
