# 配置规范 — v0.2 Web Search

## 1. 新增 Provider

```yaml
llm:
  provider: deepseek-anthropic
  base_url: https://api.deepseek.com/anthropic   # 可选，有默认值
  api_key: ${DEEPSEEK_API_KEY}
  model: deepseek-v4-pro
  temperature: 0.7
  max_tokens: 4096
  timeout: 120    # search 可能较慢，建议加大
```

### Provider 对照表

| provider | adapter | base_url | Search |
|----------|---------|----------|--------|
| `openai` | openai | `https://api.openai.com/v1` | ❌ |
| `deepseek` | openai | `https://api.deepseek.com/v1` | ❌ |
| `deepseek-anthropic` | anthropic | `https://api.deepseek.com/anthropic` | ✅ |
| `ollama` | openai | `http://localhost:11434/v1` | ❌ |

> **注意：** `deepseek` 与 `deepseek-anthropic` 是两个独立 provider，不是同一个端点的别名。

## 2. 工具配置

```yaml
tools:
  workspace: .
  enabled:
    - Read
    - Write
    - Bash
  server:
    enabled:
      - WebSearch
    web_search:
      type: web_search_20260209    # 或 web_search_20250305
      max_uses: 5
```

### 2.1 `tools.server` 字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `enabled` | list | ❌ | `[]` | 启用的 server tools |
| `web_search.type` | string | ❌ | `web_search_20260209` | Search 工具版本 |
| `web_search.max_uses` | int | ❌ | `5` | 单次对话最大搜索次数 |

### 2.2 校验规则

- `WebSearch` 仅在 `provider` 的 adapter 为 `anthropic` 时允许启用
- 若 `tools.server.enabled` 含 `WebSearch` 但 provider 为 `deepseek`（OpenAI），启动报错：

```
ConfigError: WebSearch requires anthropic adapter (use provider: deepseek-anthropic)
```

## 3. 完整配置示例

```yaml
# lumi.yaml — DeepSeek + Search

llm:
  provider: deepseek-anthropic
  api_key: ${DEEPSEEK_API_KEY}
  model: deepseek-v4-pro
  max_tokens: 4096
  timeout: 120

agent:
  max_steps: 20
  system_prompt: default
  context_window: 30        # search 产生较多消息，适当加大

tools:
  workspace: .
  enabled:
    - Read
    - Write
    - Bash
  server:
    enabled:
      - WebSearch
    web_search:
      type: web_search_20260209
      max_uses: 5
  bash:
    timeout: 30
    allowed_commands: []

logging:
  level: INFO
```

## 4. 仅本地工具（无 Search）

与 v0.1 相同，使用 OpenAI 端点：

```yaml
llm:
  provider: deepseek
  base_url: https://api.deepseek.com/v1
  model: deepseek-v4-pro
```

```yaml
tools:
  enabled: [Read, Write, Bash]
  # 无 server 段
```

## 5. 配置加载变更

```python
@dataclass
class ServerToolsConfig:
    enabled: list[str] = field(default_factory=list)
    web_search_type: str = "web_search_20260209"
    web_search_max_uses: int = 5

@dataclass
class ToolsConfig:
    enabled: list[str] = ...
    workspace: str = "."
    server: ServerToolsConfig = field(default_factory=ServerToolsConfig)
    bash_timeout: int = 30
    bash_allowed_commands: list[str] = field(default_factory=list)
```

```python
PROVIDER_DEFAULTS = {
    "openai": {"adapter": "openai", "base_url": "https://api.openai.com/v1"},
    "deepseek": {"adapter": "openai", "base_url": "https://api.deepseek.com/v1"},
    "deepseek-anthropic": {
        "adapter": "anthropic",
        "base_url": "https://api.deepseek.com/anthropic",
    },
    "ollama": {"adapter": "openai", "base_url": "http://localhost:11434/v1"},
}
```

## 6. HTTP 请求差异

### OpenAI 端点（v0.1）

```
POST {base_url}/chat/completions
Authorization: Bearer {api_key}
```

### Anthropic 端点（v0.2）

```
POST {base_url}/v1/messages
x-api-key: {api_key}
anthropic-version: 2023-06-01   # DeepSeek 忽略版本号，但建议发送
Content-Type: application/json
```

## 7. 环境变量

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（两个端点共用） |
| `LUMI_CONFIG` | 配置文件路径 |

## 8. CLI 变更

```bash
# 验证配置（含 server tool 校验）
lumi config validate

# 查看 server tools
lumi tools list
# Read: Read the contents of a file...
# Write: Write content to a file...
# Bash: Run a bash command...
# WebSearch: Search the web for current information (server-side)
```

Verbose 模式新增日志：

```
[lumi] → server: web_search (handled by provider)
[lumi] ← search results (3 hits)
[lumi] → tool: Write({"path": "notes.md", ...})
```
