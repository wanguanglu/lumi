# Lumi 模块 API 设计

## 1. 消息模型 (`messages.py`)

### 1.1 类型定义

```python
from dataclasses import dataclass, field
from typing import Literal

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class SystemMessage:
    role: Literal["system"] = "system"
    content: str = ""

@dataclass
class UserMessage:
    role: Literal["user"] = "user"
    content: str = ""

@dataclass
class AssistantMessage:
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

@dataclass
class ToolMessage:
    role: Literal["tool"] = "tool"
    tool_call_id: str = ""
    content: str = ""

Message = SystemMessage | UserMessage | AssistantMessage | ToolMessage
```

### 1.2 辅助函数

```python
def to_api_format(messages: list[Message]) -> list[dict]:
    """序列化为 OpenAI Chat Completions API 格式"""

def truncate_messages(
    messages: list[Message],
    max_count: int,
    keep_system: bool = True,
) -> list[Message]:
    """滑动窗口截断，保留 system + 最近 N 条"""
```

## 2. LLM Provider (`llm/`)

### 2.1 抽象接口

```python
# llm/base.py

from typing import Protocol

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    usage: TokenUsage | None
    raw: dict

class LLM(Protocol):
    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse: ...
```

### 2.2 OpenAI Provider

```python
# llm/openai.py

class OpenAIProvider:
    def __init__(self, config: LLMConfig): ...

    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        POST {base_url}/chat/completions

        Request body:
          model, messages, tools, temperature, max_tokens

        解析 response.choices[0].message 为 LLMResponse
        """
```

#### API 请求映射

| Lumi 字段 | OpenAI API 字段 |
|-----------|-----------------|
| `messages` | `messages` |
| `tools` | `tools`（function calling 格式） |
| `config.model` | `model` |
| `config.temperature` | `temperature` |
| `config.max_tokens` | `max_tokens` |

#### 错误类型

```python
class LLMError(Exception):
    status_code: int | None
    body: str

class LLMRateLimitError(LLMError): ...
class LLMAuthError(LLMError): ...
```

### 2.3 Provider 工厂

```python
# llm/__init__.py

def create_llm(config: LLMConfig) -> LLM:
    if config.provider == "openai":
        return OpenAIProvider(config)
    raise ConfigError(f"unknown provider: {config.provider}")
```

## 3. 工具模块 (`tools/`)

### 3.1 Tool 定义

```python
# tools/registry.py

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON Schema (OpenAI function parameters)
    handler: Callable[..., str]

class ToolRegistry:
    def __init__(self): ...
    def register(self, tool: Tool) -> None: ...
    def get(self, name: str) -> Tool | None: ...
    def schemas(self) -> list[dict]:
        """返回 OpenAI tools 格式"""
    def execute(self, name: str, arguments: dict) -> str: ...
```

OpenAI tools 格式输出示例：

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a file at the given path.",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Absolute or relative file path"
        }
      },
      "required": ["path"]
    }
  }
}
```

### 3.2 内置工具

#### `read_file`

```python
Tool(
    name="read_file",
    description="Read the contents of a file at the given path.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to read"},
        },
        "required": ["path"],
    },
    handler=read_file_handler,
)
```

行为：
- 路径不存在 → 返回 `"Error: file not found: {path}"`
- 是目录 → 返回 `"Error: {path} is a directory"`
- 文件过大（> 100KB）→ 返回 `"Error: file too large ({size} bytes, max 100KB)"`
- 成功 → 返回文件内容字符串

#### `write_file`

```python
Tool(
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
    handler=write_file_handler,
)
```

行为：
- 自动创建父目录
- 成功 → 返回 `"Successfully wrote {len(content)} bytes to {path}"`

#### `run_shell`

```python
Tool(
    name="run_shell",
    description="Execute a shell command and return its stdout/stderr.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
        },
        "required": ["command"],
    },
    handler=run_shell_handler,
)
```

行为：
- 检查 `allowed_commands` 白名单（配置为空则跳过）
- 超时 → 返回 `"Error: command timed out after {timeout}s"`
- 非零 exit code → 返回 stdout + stderr + exit code（LLM 自行判断）
- 成功 → 返回 stdout（stderr 非空时附加）

### 3.3 工具注册入口

```python
# tools/__init__.py

def create_tool_registry(config: ToolsConfig) -> ToolRegistry:
    registry = ToolRegistry()
    builtins = {
        "read_file": read_file_tool,
        "write_file": write_file_tool,
        "run_shell": make_run_shell_tool(config),
    }
    for name in config.enabled:
        registry.register(builtins[name])
    return registry
```

## 4. Agent (`agent.py`)

### 4.1 核心类

```python
class Agent:
    def __init__(
        self,
        llm: LLM,
        tools: ToolRegistry,
        config: AgentConfig,
        system_prompt: str,
        events: EventBus | None = None,
    ): ...

    def run(self, user_input: str) -> str:
        """执行单次任务，返回最终回复"""

    def chat(self, user_input: str) -> str:
        """交互模式：保留 messages 历史，多轮对话"""

    def reset(self) -> None:
        """清空对话历史（保留 system prompt）"""

    @property
    def messages(self) -> list[Message]:
        """当前消息历史（只读）"""
```

### 4.2 异常

```python
class AgentError(Exception): ...

class MaxStepsExceeded(AgentError):
    def __init__(self, max_steps: int, messages: list[Message]): ...
```

### 4.3 使用示例

```python
from lumi.config import load_config
from lumi.llm import create_llm
from lumi.tools import create_tool_registry
from lumi.agent import Agent
from lumi.prompts import load_prompt

config = load_config()
agent = Agent(
    llm=create_llm(config.llm),
    tools=create_tool_registry(config.tools),
    config=config.agent,
    system_prompt=load_prompt(config.agent.system_prompt),
)

result = agent.run("读取 README.md 并总结内容")
print(result)
```

## 5. 事件系统 (`events.py`)

```python
class EventBus:
    def on(self, event: str, handler: Callable) -> None: ...
    def emit(self, event: str, **kwargs) -> None: ...

# 内置 LoggingHandler
class LoggingHandler:
    def __init__(self, level: str = "INFO"): ...
    def attach(self, bus: EventBus) -> None: ...
```

事件 payload 约定：

| 事件 | kwargs |
|------|--------|
| `agent_start` | `user_input` |
| `agent_end` | `result`, `steps` |
| `step_start` | `step` |
| `step_complete` | `step`, `final` |
| `llm_request` | `messages`, `tools` |
| `llm_response` | `response` |
| `tool_start` | `name`, `arguments` |
| `tool_end` | `name`, `result`, `duration_ms` |
| `error` | `error`, `context` |

## 6. CLI (`cli.py`)

```python
import typer

app = typer.Typer(name="lumi", help="A minimal LLM agent harness")

@app.command()
def run(
    task: str,
    config: Path = typer.Option(None, "--config", help="Config file path"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
): ...

@app.command()
def chat(
    config: Path = typer.Option(None, "--config"),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
): ...

config_app = typer.Typer(name="config", help="Configuration commands")
app.add_typer(config_app)

@config_app.command("show")
def config_show(config: Path = typer.Option(None, "--config")): ...

@config_app.command("validate")
def config_validate(config: Path = typer.Option(None, "--config")): ...

tools_app = typer.Typer(name="tools", help="Tool management")
app.add_typer(tools_app)

@tools_app.command("list")
def tools_list(config: Path = typer.Option(None, "--config")): ...
```

### CLI 输出示例

```
$ lumi -v run "列出当前目录的 Python 文件"

[lumi] step 1/20
[lumi] → tool: run_shell({"command": "find . -name '*.py'"})
[lumi] ← tool result (142 bytes)
[lumi] step 2/20
[lumi] ✓ done (2 steps)

当前目录下的 Python 文件：
- lumi/agent.py
- lumi/cli.py
...
```

## 7. System Prompt (`prompts/default.txt`)

```
You are Lumi, a helpful AI assistant with access to tools.

You can read files, write files, and run shell commands to accomplish tasks.

Guidelines:
- Use tools when you need to interact with the filesystem or run commands.
- When a tool returns an error, analyze it and try an alternative approach.
- Be concise in your final response.
- Always explain what you did when completing a multi-step task.
```

Prompt 加载：

```python
# prompts/__init__.py 或 agent 内部

BUILTIN_PROMPTS = {"default": Path(__file__).parent / "default.txt"}

def load_prompt(name_or_path: str) -> str:
    if name_or_path in BUILTIN_PROMPTS:
        return BUILTIN_PROMPTS[name_or_path].read_text()
    path = Path(name_or_path)
    if path.exists():
        return path.read_text()
    raise ConfigError(f"system prompt not found: {name_or_path}")
```

## 8. 依赖清单

```toml
# pyproject.toml [project.dependencies]
python = ">=3.11"
httpx = ">=0.27"
pyyaml = ">=6.0"
typer = ">=0.12"
rich = ">=13.0"          # CLI 输出美化
```

开发依赖：

```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-httpx", "ruff"]
```
