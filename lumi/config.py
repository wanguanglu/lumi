from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import yaml

BUILTIN_TOOLS = frozenset({"Read", "Write", "Bash"})
TOOL_ALIASES = {
    "read_file": "Read",
    "write_file": "Write",
    "run_shell": "Bash",
    "bash": "Bash",
}
ENV_VAR_PATTERN = re.compile(r"^\$\{([A-Z_][A-Z0-9_]*)\}$")

# User-facing provider names. All listed providers use the OpenAI-compatible adapter.
PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {"adapter": "openai", "base_url": "https://api.openai.com/v1"},
    "deepseek": {"adapter": "openai", "base_url": "https://api.deepseek.com/v1"},
    "ollama": {"adapter": "openai", "base_url": "http://localhost:11434/v1"},
}


def supported_providers() -> list[str]:
    return sorted(PROVIDER_DEFAULTS)


def resolve_adapter(provider: str) -> str:
    defaults = PROVIDER_DEFAULTS.get(provider)
    if defaults is None:
        supported = ", ".join(supported_providers())
        raise ConfigError(f"unsupported provider: {provider} (supported: {supported})")
    return defaults["adapter"]


class ConfigError(Exception):
    pass


@dataclass
class LLMConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentConfig:
    max_steps: int = 20
    system_prompt: str = "default"
    context_window: int = 20


@dataclass
class ToolsConfig:
    enabled: list[str] = field(default_factory=lambda: ["Read", "Write", "Bash"])
    workspace: str = "."
    bash_timeout: int = 30
    bash_allowed_commands: list[str] = field(default_factory=list)


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "text"


@dataclass
class LumiConfig:
    llm: LLMConfig
    agent: AgentConfig
    tools: ToolsConfig
    logging: LoggingConfig


def _resolve_env(value: str) -> str:
    match = ENV_VAR_PATTERN.match(value)
    if not match:
        return value
    var_name = match.group(1)
    env_value = os.environ.get(var_name)
    if env_value is None:
        raise ConfigError(f"environment variable {var_name} is not set")
    return env_value


def _resolve_env_deep(obj: object) -> object:
    if isinstance(obj, str):
        return _resolve_env(obj)
    if isinstance(obj, dict):
        return {k: _resolve_env_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_env_deep(item) for item in obj]
    return obj


def find_config_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        if not explicit.exists():
            raise ConfigError(f"config file not found: {explicit}")
        return explicit

    env_path = os.environ.get("LUMI_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    cwd_path = Path.cwd() / "lumi.yaml"
    if cwd_path.exists():
        return cwd_path

    user_path = Path.home() / ".config" / "lumi" / "lumi.yaml"
    if user_path.exists():
        return user_path

    raise ConfigError(
        "no config file found; create lumi.yaml or set LUMI_CONFIG "
        "(see lumi.yaml.example)"
    )


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ConfigError(f"invalid base_url: {url}")


def _parse_config(data: dict) -> LumiConfig:
    llm_data = data.get("llm", {})
    agent_data = data.get("agent", {})
    tools_data = data.get("tools", {})
    logging_data = data.get("logging", {})
    bash_data = tools_data.get("bash", tools_data.get("shell", {}))

    provider = str(llm_data.get("provider", ""))
    defaults = PROVIDER_DEFAULTS.get(provider)

    llm = LLMConfig(
        provider=provider,
        base_url=str(llm_data.get("base_url") or (defaults["base_url"] if defaults else "")),
        api_key=llm_data.get("api_key", ""),
        model=llm_data.get("model", ""),
        temperature=float(llm_data.get("temperature", 0.7)),
        max_tokens=int(llm_data.get("max_tokens", 4096)),
        timeout=int(llm_data.get("timeout", 60)),
        extra_headers=dict(llm_data.get("extra_headers", {})),
    )

    agent = AgentConfig(
        max_steps=int(agent_data.get("max_steps", 20)),
        system_prompt=str(agent_data.get("system_prompt", "default")),
        context_window=int(agent_data.get("context_window", 20)),
    )

    enabled = tools_data.get("enabled")
    if enabled is None:
        enabled = ["Read", "Write", "Bash"]
    enabled = [TOOL_ALIASES.get(name, name) for name in enabled]

    tools = ToolsConfig(
        enabled=list(enabled),
        workspace=str(tools_data.get("workspace", ".")),
        bash_timeout=int(bash_data.get("timeout", 30)),
        bash_allowed_commands=list(bash_data.get("allowed_commands", [])),
    )

    logging = LoggingConfig(
        level=str(logging_data.get("level", "INFO")),
        format=str(logging_data.get("format", "text")),
    )

    return LumiConfig(llm=llm, agent=agent, tools=tools, logging=logging)


def validate_config(config: LumiConfig) -> None:
    resolve_adapter(config.llm.provider)

    _validate_url(config.llm.base_url)

    if not config.llm.api_key:
        raise ConfigError("llm.api_key must not be empty")

    if not config.llm.model:
        raise ConfigError("llm.model must not be empty")

    if config.agent.max_steps <= 0:
        raise ConfigError("agent.max_steps must be > 0")

    for name in config.tools.enabled:
        if name not in BUILTIN_TOOLS:
            raise ConfigError(f"unknown tool: {name} (available: {', '.join(sorted(BUILTIN_TOOLS))})")

    workspace = Path(config.tools.workspace)
    if not workspace.exists():
        raise ConfigError(f"tools.workspace does not exist: {workspace}")
    if not workspace.is_dir():
        raise ConfigError(f"tools.workspace is not a directory: {workspace}")


def load_config(path: Path | None = None) -> LumiConfig:
    config_path = find_config_path(path)
    with config_path.open() as f:
        raw = yaml.safe_load(f) or {}

    resolved = _resolve_env_deep(raw)
    config = _parse_config(resolved)
    validate_config(config)
    return config


def mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"
