from __future__ import annotations

from pathlib import Path

from lumi.config import ConfigError

BUILTIN_PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name_or_path: str) -> str:
    builtin_path = BUILTIN_PROMPTS_DIR / f"{name_or_path}.txt"
    if builtin_path.exists():
        return builtin_path.read_text()

    path = Path(name_or_path)
    if path.exists():
        return path.read_text()

    raise ConfigError(f"system prompt not found: {name_or_path}")
