from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lumi.config import ConfigError, load_config, mask_api_key


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "lumi.yaml"
    path.write_text(
        yaml.dump(
            {
                "llm": {
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "${TEST_API_KEY}",
                    "model": "gpt-4o",
                },
                "agent": {"max_steps": 10},
                "tools": {"enabled": ["read_file", "write_file"]},
            }
        )
    )
    return path


def test_load_config(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test-key")
    config = load_config(config_file)
    assert config.llm.model == "gpt-4o"
    assert config.llm.api_key == "sk-test-key"
    assert config.agent.max_steps == 10
    assert config.tools.enabled == ["read_file", "write_file"]


def test_missing_env_var(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="TEST_API_KEY"):
        load_config(config_file)


def test_unknown_tool(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    config_file.write_text(
        yaml.dump(
            {
                "llm": {
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "key",
                    "model": "gpt-4o",
                },
                "tools": {"enabled": ["nonexistent"]},
            }
        )
    )
    with pytest.raises(ConfigError, match="unknown tool"):
        load_config(config_file)


def test_mask_api_key() -> None:
    assert mask_api_key("sk-1234567890abcdef") == "sk-1****cdef"


def test_deepseek_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    path = tmp_path / "lumi.yaml"
    path.write_text(
        yaml.dump(
            {
                "llm": {
                    "provider": "deepseek",
                    "api_key": "${TEST_API_KEY}",
                    "model": "deepseek-chat",
                },
            }
        )
    )
    config = load_config(path)
    assert config.llm.provider == "deepseek"
    assert config.llm.base_url == "https://api.deepseek.com/v1"

