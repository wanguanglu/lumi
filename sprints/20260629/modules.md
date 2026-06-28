# 模块 API 设计 — v0.2

## 1. LLM 层扩展

### 1.1 `LLMResponse` 扩展

```python
@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]          # 仅 client tools
    usage: TokenUsage | None
    raw: dict
    server_tool_uses: int = 0           # 本轮 provider 内执行的 search 次数（观测用）
```

### 1.2 Provider 工厂

```python
# llm/__init__.py

def create_llm(config: LLMConfig) -> LLM:
    adapter = resolve_adapter(config.provider)
    if adapter == "openai":
        return OpenAIProvider(config)
    if adapter == "anthropic":
        return AnthropicProvider(config)
    raise ConfigError(f"unknown adapter: {adapter}")
```

### 1.3 `AnthropicProvider`

```python
# llm/anthropic.py

class AnthropicProvider:
    def __init__(self, config: LLMConfig, server_tools: ServerToolRegistry | None = None):
        self.config = config
        self.server_tools = server_tools or ServerToolRegistry()
        self._client = httpx.Client(timeout=config.timeout)

    def chat(self, messages: list[Message], tools: list[dict] | None = None) -> LLMResponse:
        """
        POST {base_url}/v1/messages

        内部循环处理 server_tool_use / web_search_tool_result，
        仅将 client tool_use 暴露为 tool_calls。
        """

    def close(self) -> None: ...
```

### 1.4 消息转换

```python
# llm/messages_anthropic.py

def to_anthropic_request(
    messages: list[Message],
    system_prompt: str,
    tools: list[dict],
    config: LLMConfig,
) -> dict:
    """构建 POST /v1/messages 请求体"""

def from_anthropic_response(data: dict) -> LLMResponse:
    """解析响应，分离 client tool_calls 与 server blocks"""

def extract_text_blocks(content: list[dict]) -> str:
    """从 content blocks 拼接文本"""

def extract_client_tool_calls(content: list[dict]) -> list[ToolCall]:
    """提取 type=tool_use 的 blocks"""

def has_server_tool_activity(content: list[dict]) -> bool:
    """是否含 server_tool_use 或 web_search_tool_result"""
```

#### Anthropic 请求体示例

```json
{
  "model": "deepseek-v4-pro",
  "max_tokens": 4096,
  "system": "You are Lumi...",
  "messages": [
    {
      "role": "user",
      "content": [{"type": "text", "text": "今天北京天气怎么样？"}]
    }
  ],
  "tools": [
    {
      "type": "web_search_20260209",
      "name": "web_search",
      "max_uses": 5
    },
    {
      "name": "Read",
      "description": "Read file...",
      "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"]
      }
    }
  ]
}
```

#### Client tool schema 格式差异

| OpenAI (v0.1) | Anthropic (v0.2) |
|---------------|------------------|
| `type: function` | 直接 `name` + `input_schema` |
| `function.parameters` | `input_schema` |
| `function.name` | `name` |

`ToolRegistry.schemas()` 需新增 `schemas_anthropic()` 方法，或 Provider 内转换。

## 2. Server Tools 模块

### 2.1 目录结构

```
tools/server/
├── __init__.py
├── registry.py      # ServerToolRegistry
└── web_search.py    # WebSearch tool schema
```

### 2.2 `ServerToolRegistry`

```python
@dataclass
class ServerTool:
    name: str                    # 配置名：WebSearch
    api_type: str                # API type：web_search_20260209
    schema: dict                 # 发给 API 的 tool 定义

class ServerToolRegistry:
    def register(self, tool: ServerTool) -> None: ...
    def schemas(self) -> list[dict]:
        """返回 Anthropic API tools 数组（含 server tool types）"""
```

与 `ToolRegistry` 分离：**ServerToolRegistry 无 execute 方法**。

### 2.3 `WebSearch`

```python
# tools/server/web_search.py

def make_web_search_tool(config: ServerToolsConfig) -> ServerTool:
    return ServerTool(
        name="WebSearch",
        api_type=config.web_search_type,
        schema={
            "type": config.web_search_type,
            "name": "web_search",
            "max_uses": config.web_search_max_uses,
        },
    )
```

### 2.4 工厂入口

```python
# tools/server/__init__.py

BUILTIN_SERVER_TOOLS = {"WebSearch": make_web_search_tool}

def create_server_tool_registry(config: ServerToolsConfig) -> ServerToolRegistry:
    registry = ServerToolRegistry()
    for name in config.enabled:
        registry.register(BUILTIN_SERVER_TOOLS[name](config))
    return registry
```

## 3. Agent 改造

### 3.1 构造函数

```python
class Agent:
    def __init__(
        self,
        llm: LLM,
        tools: ToolRegistry,
        config: AgentConfig,
        system_prompt: str,
        server_tools: ServerToolRegistry | None = None,  # 新增
        events: EventBus | None = None,
    ):
        self._tool_schemas = tools.schemas()
        self._server_tool_schemas = server_tools.schemas() if server_tools else []
```

### 3.2 请求 tools 合并

```python
def _all_tool_schemas(self) -> list[dict]:
    # OpenAI provider: 仅 client schemas（OpenAI 格式）
    # Anthropic provider: client (anthropic 格式) + server schemas
    if isinstance(self.llm, AnthropicProvider):
        return (
            self.tools.schemas_anthropic()
            + self._server_tool_schemas
        )
    return self._tool_schemas
```

### 3.3 循环体

Agent 主循环 **逻辑不变**，仅 `_all_tool_schemas()` 替换 `self._tool_schemas`。

## 4. CLI 组装

```python
def _build_agent(config_path, verbose) -> Agent:
    config = load_config(config_path)
    server_tools = create_server_tool_registry(config.tools.server)
    llm = create_llm(config.llm, server_tools=server_tools)

    return Agent(
        llm=llm,
        tools=create_tool_registry(config.tools),
        server_tools=server_tools,
        config=config.agent,
        system_prompt=load_prompt(config.agent.system_prompt),
        events=events,
    )
```

## 5. Events 扩展

| 事件 | kwargs | 说明 |
|------|--------|------|
| `server_tool_start` | `name`, `type` | Provider 内 search 开始 |
| `server_tool_end` | `name`, `results_count` | Provider 内 search 完成 |

CLI verbose 输出：

```
[lumi] → server: WebSearch
[lumi] ← server: WebSearch (3 results)
[lumi] → tool: Write({"path": "notes.md"})
```

## 6. `ToolRegistry` 扩展

新增 Anthropic 格式 schema 输出：

```python
def schema_anthropic(self) -> dict:
    return {
        "name": self.name,
        "description": self.description,
        "input_schema": self.parameters,
    }

def schemas_anthropic(self) -> list[dict]:
    return [tool.schema_anthropic() for tool in self._tools.values()]
```

## 7. 测试策略

```
tests/
├── test_anthropic.py          # Provider mock HTTP
├── test_messages_anthropic.py # 消息转换
├── test_server_tools.py       # WebSearch schema
└── test_agent_search.py       # 集成 MockLLM + search 场景
```

### 7.1 `test_anthropic.py` 用例

- 纯文本响应解析
- client tool_use 提取
- server_tool_use + web_search_tool_result 内循环
- client + server 混合响应
- 401 / 400 错误映射
- x-api-key header

### 7.2 Mock 响应示例

```python
# search 完成后返回文本
{
  "content": [
    {"type": "server_tool_use", "id": "srv_1", "name": "web_search"},
    {"type": "web_search_tool_result", "tool_use_id": "srv_1", "content": [...]},
    {"type": "text", "text": "根据搜索结果，北京今天..."}
  ],
  "stop_reason": "end_turn"
}
```

## 8. 依赖变更

无新运行时依赖，仍用 `httpx`。

可选 dev 依赖：更多 pytest fixture。

## 9. Prompt 更新

`prompts/default.txt` 补充：

```
You can search the web for current information when needed.
Use WebSearch for questions about recent events, weather, or live data.
Use Read/Write/Bash for local file operations.
```
