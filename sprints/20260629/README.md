# Lumi Sprint — 2026-06-29

> DeepSeek Web Search · Anthropic Provider · Server-side Tools

## Sprint 目标

为 lumi 增加 **DeepSeek Anthropic 端点** 支持，接入 **Web Search** 服务端工具，使 agent 能联网查询信息，同时保留现有本地工具（Read / Write / Bash）。

**v0.2 交付标准：** 配置 `provider: deepseek-anthropic` 后，可通过 CLI 完成需要联网搜索的任务，并与本地文件工具组合使用。

### Demo 验收任务

```bash
lumi run "搜索 DeepSeek v4 最新发布信息，总结要点写入 notes.md"
```

```bash
lumi chat
> 今天北京天气怎么样？
> /quit
```

## 背景与动机

| 端点 | 协议 | Search |
|------|------|--------|
| `api.deepseek.com/v1` | OpenAI Chat Completions | ❌ |
| `api.deepseek.com/anthropic` | Anthropic Messages API | ✅ `web_search_*` |

v0.1 仅实现 OpenAI-compatible adapter，**不能**通过改 `base_url` 启用 search。需要新增 Anthropic adapter，并区分 **本地工具** 与 **服务端工具** 两类执行模型。

## 设计原则

1. **Adapter 分离** — OpenAI / Anthropic 各一套 Provider，Agent 仍只依赖 `LLM` Protocol
2. **Server tools ≠ Client tools** — Search 在 DeepSeek 服务端执行，不经过 `ToolRegistry.execute()`
3. **Agent 改动最小** — 尽量在 Provider 内消化 server tool 循环，Agent 只处理 client tool_calls
4. **配置显式** — `deepseek` 与 `deepseek-anthropic` 是两个 provider，不隐式切换
5. **可组合** — 同一 agent 可同时启用 WebSearch + Read/Write/Bash

## 文档索引

| 文档 | 内容 |
|------|------|
| [architecture.md](./architecture.md) | 双 Adapter 架构、Search 数据流、Agent 改造点 |
| [configuration.md](./configuration.md) | Provider 配置、web_search 参数 |
| [modules.md](./modules.md) | AnthropicProvider、消息映射、ServerTool 模块 |
| [roadmap.md](./roadmap.md) | 实现阶段、里程碑、风险 |

## 与 v0.1 的关系

```
v0.1 (已完成)                    v0.2 (本 Sprint)
─────────────────                ─────────────────
OpenAIProvider                   + AnthropicProvider
Read / Write / Bash              + WebSearch (server)
deepseek → OpenAI 端点            + deepseek-anthropic → Anthropic 端点
Agent ReAct 循环                  Agent 小改（client/server 分流）
```

v0.1 代码路径保持不变；v0.2 为 **增量扩展**，不破坏现有 OpenAI 链路。

## 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 新 provider 名 | `deepseek-anthropic` | 与 `deepseek`（OpenAI）区分清晰 |
| HTTP 实现 | httpx 直调 REST | 与 v0.1 一致，不引入 anthropic SDK |
| Search 工具类型 | `web_search_20260209` | DeepSeek 官方支持，较新版本 |
| Server tool 循环位置 | Provider 内部 | Agent 不感知 server tool 细节 |
| 是否支持 OpenAI 端点 search | 否 | DeepSeek 未在 OpenAI 端点暴露 search |

## 项目结构（v0.2 增量）

```
lumi/
├── llm/
│   ├── base.py              # 扩展 LLMResponse
│   ├── openai.py            # 不变
│   ├── anthropic.py         # 新增
│   └── messages_anthropic.py # Anthropic ↔ Lumi 消息转换
├── tools/
│   ├── server/              # 新增：服务端工具 schema
│   │   ├── __init__.py
│   │   └── web_search.py
│   └── ...                  # Read / Write / Bash 不变
└── agent.py                 # 小改：合并 client + server tool schemas
```
