# Lumi 架构设计

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                         CLI                              │
│              lumi run / lumi chat / lumi tools           │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                        Agent                             │
│   ┌─────────────────────────────────────────────────┐   │
│   │              ReAct Loop (max_steps)              │   │
│   │  messages → LLM → tool_calls? → execute → loop  │   │
│   └─────────────────────────────────────────────────┘   │
│                          │                               │
│         ┌────────────────┼────────────────┐             │
│         ▼                ▼                ▼             │
│    Event Hooks      Tool Registry      Context Mgr       │
└─────────┬────────────────┬──────────────────────────────┘
          │                │
┌─────────▼────────┐  ┌────▼──────────────────────────────┐
│   LLM Provider   │  │           Tools                    │
│  (OpenAI-compat) │  │  read_file / write_file / shell    │
└─────────┬────────┘  └───────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────┐
│              OpenAI-compatible HTTP API                  │
│     (OpenAI / Azure / Ollama / vLLM / 自定义网关)        │
└─────────────────────────────────────────────────────────┘
```

## 2. Agent 主循环

Agent 采用标准 **ReAct** 模式，是整个 harness 的核心。

### 2.1 循环伪代码

```python
def run(user_input: str) -> str:
    messages.append(UserMessage(user_input))

    for step in range(max_steps):
        emit("step_start", step=step)

        response = llm.chat(messages, tools=registry.schemas())
        messages.append(response.message)

        if not response.tool_calls:
            emit("step_complete", step=step, final=True)
            return response.content

        for call in response.tool_calls:
            emit("tool_start", name=call.name, args=call.arguments)
            try:
                result = registry.execute(call.name, call.arguments)
            except Exception as e:
                result = f"Error: {e}"
            emit("tool_end", name=call.name, result=result)
            messages.append(ToolMessage(call.id, result))

        emit("step_complete", step=step, final=False)

    raise MaxStepsExceeded(max_steps)
```

### 2.2 终止条件

| 条件 | 行为 |
|------|------|
| LLM 返回纯文本，无 tool_calls | 正常结束，返回 content |
| 达到 `max_steps` | 抛出 `MaxStepsExceeded`，CLI 友好提示 |
| LLM API 错误 | 抛出 `LLMError`，保留已有 messages 供调试 |
| 用户中断 (Ctrl+C) | 优雅退出，打印当前 step 数 |

### 2.3 设计约束

- **单线程同步**：v0.1 不做 async，降低复杂度
- **无并行 tool call**：v0.1 顺序执行同一轮的所有 tool_calls（OpenAI 可能返回多个）
- **状态不可变消息**：每步 append 新 message，不修改历史（便于调试和后续持久化）

## 3. 模块职责

### 3.1 `messages.py` — 消息模型

统一 agent 状态的数据结构，对齐 OpenAI Chat Completions 格式。

```
Message
├── SystemMessage(content)
├── UserMessage(content)
├── AssistantMessage(content, tool_calls?)
└── ToolMessage(tool_call_id, content)
```

辅助方法：
- `messages_to_api()` — 序列化为 API 请求格式
- `estimate_tokens()` — 粗略 token 估算（v0.1 按字符数）

### 3.2 `llm/` — Provider 层

```
LLM (Protocol)
└── OpenAIProvider
    ├── chat(messages, tools) → LLMResponse
    └── 支持 streaming（v0.1 可选，CLI 体验提升）
```

`LLMResponse` 结构：

```python
@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    usage: TokenUsage | None
    raw: dict  # 原始 API 响应，调试用
```

Provider 从配置文件实例化，Agent 只依赖 `LLM` 协议。

### 3.3 `tools/` — 工具系统

```
ToolRegistry
├── register(tool: Tool)
├── schemas() → list[dict]       # OpenAI function calling 格式
└── execute(name, arguments) → str
```

每个 Tool 定义：

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict          # JSON Schema
    handler: Callable[..., str]
```

v0.1 内置工具见 [modules.md](./modules.md#工具模块)。

### 3.4 `config.py` — 配置加载

- 读取 YAML 配置文件（默认 `lumi.yaml`）
- 环境变量插值（`${OPENAI_API_KEY}`）
- Pydantic 或 dataclass 校验
- CLI `--config` 覆盖默认路径

详见 [configuration.md](./configuration.md)。

### 3.5 `events.py` — 事件 Hook

轻量观察者模式，不引入 heavy 依赖：

```python
# 内置事件
on_agent_start
on_agent_end
on_step_start
on_step_complete
on_llm_request
on_llm_response
on_tool_start
on_tool_end
on_error
```

CLI 默认注册一个 `LoggingHandler`；用户可注册自定义 handler。

### 3.6 `cli.py` — 命令行入口

| 命令 | 说明 |
|------|------|
| `lumi run "<task>"` | 单次任务，执行后退出 |
| `lumi chat` | 交互式 REPL，多轮对话 |
| `lumi tools list` | 列出已注册工具 |
| `lumi config show` | 打印当前有效配置（密钥脱敏） |

全局选项：`--config PATH`、`-v/--verbose`

## 4. Context 管理

v0.1 采用最简单的 **滑动窗口截断**：

```
保留: [system] + [最近 N 轮对话]
丢弃: 更早的 user/assistant/tool 消息
```

配置项 `agent.context_window`（默认 20 条消息）。

截断在每次 LLM 请求前执行，对 Agent 循环透明。

> v0.2 可考虑 summarize 旧消息，v0.1 不做。

## 5. 错误处理策略

| 场景 | 策略 |
|------|------|
| Tool 执行异常 | 捕获，返回 `"Error: {message}"` 作为 tool result |
| Tool 不存在 | 返回 `"Error: unknown tool '{name}'"` |
| JSON 参数解析失败 | 返回 parse error，让 LLM 修正 |
| LLM API 4xx/5xx | 抛出 `LLMError`，附带 status 和 body |
| 网络超时 | 可配置 `llm.timeout`，默认 60s，超时抛 `LLMError` |
| max_steps 耗尽 | 抛 `MaxStepsExceeded`，建议用户简化任务 |

原则：**工具层错误不回传用户，而是回传 LLM 让其自行决策**；只有 LLM 层和网络层错误才中断 agent。

## 6. 数据流示例

任务：`"读取 README.md 并总结"`

```
Step 0:
  UserMessage("读取 README.md 并总结")
  → LLM → AssistantMessage(tool_calls=[read_file("README.md")])

Step 1:
  ToolMessage("# Lumi\n\nA minimal agent harness...")
  → LLM → AssistantMessage("这是一个极简 LLM agent harness...")

Done. Return content.
```

## 7. 扩展点（预留，v0.1 不实现）

| 扩展点 | 接口 | 预期版本 |
|--------|------|----------|
| 新 LLM Provider | 实现 `LLM` Protocol | v0.2 |
| 自定义 Tool | `registry.register()` | v0.1 ✅ |
| Session 持久化 | `SessionStore` Protocol | v0.2 |
| MCP 工具接入 | `MCPToolAdapter` | v0.3 |
| Async 执行 | `async def run()` | v0.2 |
| Streaming 输出 | `llm.chat_stream()` | v0.1 可选 |
