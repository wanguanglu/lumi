# Lumi 配置规范

## 1. 概述

Lumi 通过 **YAML 配置文件** 管理运行时参数。密钥等敏感信息通过 **环境变量** 注入，不写入配置文件。

### 配置文件查找顺序

1. CLI 参数 `--config /path/to/lumi.yaml`
2. 环境变量 `LUMI_CONFIG`
3. 当前工作目录 `./lumi.yaml`
4. 用户目录 `~/.config/lumi/lumi.yaml`

找到第一个存在的文件即停止。

## 2. 完整配置示例

```yaml
# lumi.yaml

llm:
  provider: openai                    # v0.1 仅支持 openai
  base_url: https://api.openai.com/v1 # OpenAI-compatible 端点
  api_key: ${OPENAI_API_KEY}          # 环境变量插值
  model: gpt-4o
  temperature: 0.7
  max_tokens: 4096
  timeout: 60                         # 秒
  # extra_headers:                    # 可选，自定义网关鉴权
  #   X-Custom-Auth: ${CUSTOM_TOKEN}

agent:
  max_steps: 20
  system_prompt: default              # 内置 prompt 名，或文件路径
  context_window: 20                # 保留最近 N 条消息

tools:
  enabled:
    - read_file
    - write_file
    - run_shell
  shell:
    timeout: 30                       # shell 命令超时（秒）
    allowed_commands:                 # 白名单，空 = 允许所有（开发模式）
      - ls
      - cat
      - grep
      - find
      - python
      - pip

logging:
  level: INFO                         # DEBUG | INFO | WARNING | ERROR
  format: text                        # text | json
```

## 3. 配置项说明

### 3.1 `llm` — LLM Provider

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `provider` | string | ✅ | — | Provider 类型，v0.1 固定 `openai` |
| `base_url` | string | ✅ | — | API 根路径，需含 `/v1` |
| `api_key` | string | ✅ | — | API 密钥，支持 `${ENV_VAR}` |
| `model` | string | ✅ | — | 模型名称 |
| `temperature` | float | ❌ | `0.7` | 采样温度 |
| `max_tokens` | int | ❌ | `4096` | 单次回复最大 token |
| `timeout` | int | ❌ | `60` | HTTP 请求超时（秒） |
| `extra_headers` | map | ❌ | `{}` | 附加 HTTP 请求头 |

#### 常见 Provider 配置

**OpenAI 官方：**
```yaml
llm:
  provider: openai
  base_url: https://api.openai.com/v1
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o
```

**Azure OpenAI：**
```yaml
llm:
  provider: openai
  base_url: https://{resource}.openai.azure.com/openai/deployments/{deployment}
  api_key: ${AZURE_OPENAI_API_KEY}
  model: gpt-4o                        # deployment name
  extra_headers:
    api-key: ${AZURE_OPENAI_API_KEY}
```

**Ollama（本地）：**
```yaml
llm:
  provider: openai
  base_url: http://localhost:11434/v1
  api_key: ollama                      # Ollama 不校验，填任意值
  model: llama3.1
```

**vLLM / 自建网关：**
```yaml
llm:
  provider: openai
  base_url: http://localhost:8000/v1
  api_key: ${VLLM_API_KEY}
  model: meta-llama/Llama-3.1-8B-Instruct
```

**DeepSeek / 其他 OpenAI-compatible：**
```yaml
llm:
  provider: openai
  base_url: https://api.deepseek.com/v1
  api_key: ${DEEPSEEK_API_KEY}
  model: deepseek-chat
```

### 3.2 `agent` — Agent 行为

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `max_steps` | int | ❌ | `20` | ReAct 循环最大步数 |
| `system_prompt` | string | ❌ | `default` | 内置名或 `.txt`/`.md` 文件路径 |
| `context_window` | int | ❌ | `20` | 上下文消息保留条数 |

#### system_prompt 解析规则

1. 若为内置名（如 `default`）→ 加载 `lumi/prompts/{name}.txt`
2. 若为相对/绝对文件路径 → 读取该文件内容
3. 文件不存在 → 启动时报错

### 3.3 `tools` — 工具配置

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `enabled` | list[string] | ❌ | 全部内置 | 启用的工具名列表 |
| `shell.timeout` | int | ❌ | `30` | Shell 命令超时 |
| `shell.allowed_commands` | list[string] | ❌ | `[]`（全允许） | 命令白名单 |

> **安全提示：** 生产环境务必配置 `allowed_commands` 白名单。空列表在 v0.1 表示开发模式，允许任意命令。

### 3.4 `logging` — 日志

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `level` | string | ❌ | `INFO` | 日志级别 |
| `format` | string | ❌ | `text` | `text` 或 `json` |

## 4. 环境变量

### 4.1 配置相关

| 变量 | 说明 |
|------|------|
| `LUMI_CONFIG` | 配置文件路径 |
| `OPENAI_API_KEY` | 常用 API 密钥（配置中引用） |

### 4.2 环境变量插值

配置值支持 `${VAR_NAME}` 语法：

```yaml
api_key: ${OPENAI_API_KEY}
```

规则：
- 仅支持完整值替换（不支持 `"prefix-${KEY}-suffix"`）
- 变量未设置 → 启动时报 `ConfigError: environment variable OPENAI_API_KEY is not set`
- 不支持默认值语法（v0.1 保持简单）

## 5. 配置加载实现

```python
# config.py 核心结构

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
    enabled: list[str] = field(default_factory=lambda: ["read_file", "write_file", "run_shell"])
    shell_timeout: int = 30
    shell_allowed_commands: list[str] = field(default_factory=list)

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

def load_config(path: Path | None = None) -> LumiConfig: ...
```

### 校验规则

启动时执行以下校验，失败则 `ConfigError` 退出：

- [ ] `llm.provider` 必须为 `openai`（v0.1）
- [ ] `llm.base_url` 必须是合法 URL
- [ ] `llm.api_key` 非空
- [ ] `llm.model` 非空
- [ ] `agent.max_steps` > 0
- [ ] `tools.enabled` 中每个名称必须存在于内置工具集
- [ ] `system_prompt` 文件路径必须可读（若为文件路径）

## 6. 示例文件

项目根目录提供 `lumi.yaml.example`（可提交 git），用户复制为 `lumi.yaml`（加入 `.gitignore`）。

```gitignore
# .gitignore
lumi.yaml
.env
```

## 7. CLI 配置命令

```bash
# 查看当前有效配置（api_key 脱敏为 sk-****xxxx）
lumi config show

# 指定配置文件
lumi --config ./dev.yaml run "hello"

# 验证配置文件
lumi config validate --config ./lumi.yaml
```

`config validate` 仅做加载和校验，不调用 LLM API。
