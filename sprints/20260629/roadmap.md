# 路线图 — v0.2 Web Search

## 交付清单

- [ ] `PROVIDER_DEFAULTS` 增加 `deepseek-anthropic`
- [ ] `ServerToolsConfig` + 配置解析与校验
- [ ] `llm/messages_anthropic.py` 消息双向转换
- [ ] `llm/anthropic.py` Provider（含 server tool 内循环）
- [ ] `tools/server/` WebSearch schema
- [ ] `ToolRegistry.schemas_anthropic()`
- [ ] Agent 合并 client + server tool schemas
- [ ] Events: `server_tool_start` / `server_tool_end`
- [ ] CLI `tools list` 显示 server tools
- [ ] 更新 `lumi.yaml.example`（deepseek-anthropic 示例）
- [ ] 测试（anthropic provider、server tools、agent 集成）
- [ ] Demo 验收通过

## 实现阶段

### Phase 1 — 基础设施（Day 1）

```
config.py          新增 deepseek-anthropic、ServerToolsConfig、校验
llm/messages_anthropic.py   消息转换（纯函数，易测）
tools/server/      WebSearch schema + registry
ToolRegistry.schemas_anthropic()
```

**验收：** 单元测试通过，config validate 支持新 provider。

### Phase 2 — AnthropicProvider（Day 2）

```
llm/anthropic.py   HTTP 请求 + 响应解析
                   server tool 内循环
llm/__init__.py    工厂注册
tests/test_anthropic.py
```

**验收：** mock HTTP 测试覆盖 text / tool_use / web_search 场景。

### Phase 3 — Agent 集成（Day 3）

```
agent.py           合并 schemas，循环逻辑微调
events.py          server tool 事件
cli.py             组装 server_tools
prompts/default.txt  更新
```

**验收：** MockLLM 集成测试通过。

### Phase 4 — 端到端（Day 4）

```
真实 API 测试（DeepSeek + Search）
Demo 任务跑通
README 更新
lumi.yaml.example 更新
```

**验收：**

```bash
lumi run "搜索 DeepSeek v4 新特性，写入 notes.md"
lumi chat
> 今天有什么科技新闻？
```

## 里程碑

```
2026-06-29  Sprint 设计文档 ✅
2026-06-30  Phase 1 配置 + 消息转换
2026-07-01  Phase 2 AnthropicProvider
2026-07-02  Phase 3 Agent 集成
2026-07-03  Phase 4 E2E + v0.2 tag
```

## 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| DeepSeek search API 行为与文档不一致 | Provider 内循环逻辑需调整 | Phase 2 先用真实 API 验证，再写测试 mock |
| server + client tool 同轮响应 | 解析复杂 | Provider 内优先处理 server blocks |
| Anthropic 消息格式与 OpenAI 差异大 | messages.py 膨胀 | 独立 messages_anthropic.py，不污染现有模型 |
| search 延迟高 | 用户体验差 | timeout 默认 120s；v0.2.1 加 streaming |
| web_search 版本变更 | schema 失效 | 配置化 type 字段，默认 20260209 |

## 明确不做（v0.2）

| 功能 | 计划版本 |
|------|----------|
| Streaming search 进度 | v0.2.1 |
| 真实 Anthropic Claude API | v0.3 |
| OpenAI 端点 search | 不做（DeepSeek 不支持） |
| 多 server tool（code execution） | 不做（DeepSeek 不支持） |
| 搜索结果缓存 | v0.3 |
| 自动选择 OpenAI vs Anthropic 端点 | 不做（配置显式） |

## 成功指标

| 指标 | 目标 |
|------|------|
| 新增核心代码 | < 400 行 |
| Anthropic provider 测试 | ≥ 8 个 case |
| Search demo 成功率 | 连续 3 次成功 |
| 现有 v0.1 测试 | 全部仍 pass（无回归） |
| Search 端到端延迟 | < 30s（网络正常） |

## 开放问题

1. **Provider 内循环上限** — server tool 多轮是否设 max_inner_steps（建议 5）？
2. **search 结果是否写入 messages** — 完整 block 还是摘要？（建议完整 block，保证多轮对话上下文）
3. **deepseek-anthropic 是否作为默认 deepseek 配置** — 建议否，用户显式选择
4. **thinking 模式** — DeepSeek Anthropic 端点支持 thinking block，v0.2 是否接入？（建议 v0.2.1）
