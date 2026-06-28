# 架构设计 — Web Search & Anthropic Provider

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                           CLI                                │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                          Agent                               │
│              ReAct Loop (client tools only)                  │
└────────┬───────────────────────────────────┬────────────────┘
         │                                   │
┌────────▼────────┐                 ┌────────▼────────────────┐
│ AnthropicProvider│                 │     ToolRegistry         │
│  ┌─────────────┐│                 │  Read / Write / Bash     │
│  │ Inner Loop  ││                 │  (client-side execute)   │
│  │ server tool ││                 └─────────────────────────┘
│  │ handling    ││
│  └─────────────┘│
└────────┬────────┘
         │
┌────────▼────────────────────────────────────────────────────┐
│         POST https://api.deepseek.com/anthropic/v1/messages  │
│         tools: [web_search_20260209, Read, Write, Bash]      │
└─────────────────────────────────────────────────────────────┘
```

## 2. 两类工具模型

### 2.1 Client Tools（本地执行）

与 v0.1 相同，由 lumi 在本地执行：

| 工具 | 执行者 | 结果回传 |
|------|--------|----------|
| Read | lumi `ToolRegistry` | `ToolMessage` |
| Write | lumi `ToolRegistry` | `ToolMessage` |
| Bash | lumi `ToolRegistry` | `ToolMessage` |

### 2.2 Server Tools（服务端执行）

由 DeepSeek 在服务端执行，lumi **不调用 execute()**：

| 工具 | 类型 | 执行者 |
|------|------|--------|
| WebSearch | `web_search_20260209` | DeepSeek API |

API 返回的消息 block 类型：

```
assistant content blocks:
  - text
  - tool_use              ← client tool（Read/Write/Bash）
  - server_tool_use       ← search 开始
  - web_search_tool_result ← search 结果（DeepSeek 已执行完）
```

### 2.3 关键区别

```
Client tool 流程:
  LLM → tool_use → lumi execute → tool_result → LLM

Server tool 流程:
  LLM → server_tool_use → DeepSeek 执行 → web_search_tool_result → LLM
  （全程在 Provider 内部或 API 单次响应中完成）
```

## 3. AnthropicProvider 内部循环

Provider 负责消化 server tool，对 Agent 暴露统一的 `LLMResponse`：

```python
def chat(self, messages, tools) -> LLMResponse:
    anthropic_messages = to_anthropic_format(messages)
    api_tools = self._merge_tools(tools)  # client schemas + web_search

    while True:
        response = self._post_messages(anthropic_messages, api_tools)
        blocks = response["content"]

        client_tool_calls = extract_tool_use(blocks)
        server_blocks = extract_server_blocks(blocks)

        if server_blocks and not client_tool_calls:
            # Search 等 server tool 已完成，结果已在 blocks 里
            # 追加 assistant message，继续让模型消化搜索结果
            anthropic_messages.append({"role": "assistant", "content": blocks})
            if has_final_text(blocks):
                return to_llm_response(blocks)
            continue

        if client_tool_calls:
            # 返回给 Agent 本地执行
            return LLMResponse(
                content=extract_text(blocks),
                tool_calls=client_tool_calls,
                ...
            )

        # 纯文本，结束
        return LLMResponse(content=extract_text(blocks), tool_calls=[], ...)
```

> **设计意图：** Agent 循环逻辑几乎不变，server tool 的 multi-step 由 Provider 内循环处理。

## 4. Agent 改造（最小）

### 4.1 工具 schema 合并

```python
# agent.py 或 cli _build_agent
client_schemas = tools.schemas()           # Read/Write/Bash
server_schemas = server_tools.schemas()    # WebSearch
all_schemas = client_schemas + server_schemas

response = llm.chat(context, tools=all_schemas)
# Agent 仍只 execute client tool_calls
```

### 4.2 Agent 循环不变

```python
for call in response.tool_calls:
    # 只有 client tools 会到这里
    result = self.tools.execute(call.name, call.arguments)
    self._messages.append(ToolMessage(...))
```

Server tool 结果已在 Provider 内写入 assistant 消息历史（或 Provider 返回的 content 已包含搜索摘要）。

### 4.3 消息历史扩展

Anthropic 格式要求完整保留 `tool_use` / `tool_result` / `web_search_tool_result` blocks。需要扩展 `messages.py`：

```python
@dataclass
class AssistantMessage:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_blocks: list[dict] | None = None   # Anthropic content blocks 原样保留
```

`raw_blocks` 仅在 Anthropic provider 时使用，OpenAI provider 忽略。

## 5. 消息格式映射

### 5.1 Lumi → Anthropic

| Lumi | Anthropic |
|------|-----------|
| `SystemMessage` | `system` 参数（独立字段） |
| `UserMessage` | `{"role":"user","content":[{"type":"text","text":"..."}]}` |
| `AssistantMessage.tool_calls` | `{"type":"tool_use", "id", "name", "input"}` |
| `ToolMessage` | `{"type":"tool_result", "tool_use_id", "content"}` |

### 5.2 Anthropic → Lumi

| Anthropic block | Lumi |
|-----------------|------|
| `text` | `AssistantMessage.content` |
| `tool_use` | `ToolCall` |
| `server_tool_use` | Provider 内部处理，不入 Agent tool_calls |
| `web_search_tool_result` | Provider 内部处理，可选摘要写入 content |

## 6. Web Search 工具定义

DeepSeek Anthropic 端点接受的 server tool schema：

```json
{
  "type": "web_search_20260209",
  "name": "web_search",
  "max_uses": 5
}
```

与 Anthropic 官方 Claude web search 工具格式一致。DeepSeek 文档确认支持：

- `server_tool_use`
- `web_search_tool_result`

不支持：`code_execution`、`mcp_tool_use` 等。

## 7. 完整数据流示例

任务：`"搜索 Python 3.13 新特性，写入 summary.md"`

```
Step 0 — User
  UserMessage("搜索 Python 3.13 新特性，写入 summary.md")

Step 1 — Provider inner loop
  → POST /v1/messages (tools: [web_search, Read, Write, Bash])
  ← assistant blocks: [server_tool_use, web_search_tool_result, text("我找到了...")]
  Provider 内继续 / 或返回 content + 空 tool_calls

Step 2 — Agent (client tool)
  ← tool_use: Write(path="summary.md", content="...")
  → ToolMessage("Successfully wrote...")
  
Step 3 — Agent
  ← text("已将 Python 3.13 新特性写入 summary.md")
  Done.
```

## 8. 错误处理

| 场景 | 策略 |
|------|------|
| Search 失败 | Provider 将 error block 转为 LLMError 或 content 警告 |
| Search + client tool 同轮 | 先处理 server blocks，再返回 client tool_calls |
| Anthropic 端点 400 | 同 OpenAIProvider，解析 error.message |
| web_search max_uses 耗尽 | API 返回错误，Provider 抛 LLMError |
| 混用 deepseek OpenAI 端点 + web_search 配置 | 启动校验报错 |

## 9. 不做的事（本 Sprint）

- Streaming search 进度展示
- OpenAI 端点 search（DeepSeek 不支持）
- 真实 Anthropic Claude API（可 v0.3 扩展同一 AnthropicProvider）
- 多 server tool 组合（code execution 等 DeepSeek 不支持）
