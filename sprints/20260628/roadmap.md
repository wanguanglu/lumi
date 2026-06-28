# Lumi 路线图

## v0.1 — MVP（本 Sprint）

**目标：** 可运行的极简 agent harness，CLI 端到端 demo 通过。

### 交付清单

- [ ] 项目脚手架（`pyproject.toml`、包结构、`.gitignore`）
- [ ] 配置系统（YAML 加载、环境变量插值、校验）
- [ ] 消息模型（4 种 message 类型、API 序列化）
- [ ] OpenAI-compatible LLM Provider（`httpx` 直调 REST）
- [ ] Tool Registry + 3 个内置工具（read/write/shell）
- [ ] Agent ReAct 循环（max_steps、context 截断）
- [ ] 事件 Hook + LoggingHandler
- [ ] CLI（`run` / `chat` / `config` / `tools`）
- [ ] 默认 system prompt
- [ ] 基础测试（config、tools、agent mock LLM）
- [ ] `lumi.yaml.example` + README

### Demo 验收任务

以下任务必须能一次性跑通：

```
lumi run "读取当前目录结构，找出所有 .py 文件，写入 files.txt"
```

```
lumi chat
> 你好
> 帮我看看 pyproject.toml 里定义了哪些依赖
> exit
```

### 明确不做（v0.1）

| 功能 | 原因 | 计划版本 |
|------|------|----------|
| Async / streaming | 增加复杂度，同步够用 | v0.1.1 或 v0.2 |
| 多 Provider | 先做好 OpenAI-compat | v0.2 |
| Session 持久化 | 无明确需求 | v0.2 |
| 向量记忆 / RAG | 独立子系统 | v0.3+ |
| MCP 协议 | 工具层扩展 | v0.3 |
| Web UI | CLI 优先 | 待定 |
| 多 Agent 协作 | 超出「极简」范围 | 不做 |
| Docker / 沙箱 | shell 白名单够用 | v0.2 |
| Plugin 系统 | 直接 register tool 即可 | 不做 |

---

## v0.1.1 — 体验 polish

- [ ] LLM streaming 输出（CLI 逐字显示）
- [ ] `--dry-run` 模式（打印 LLM 请求不发送）
- [ ] 更友好的错误信息（LLM 401/429 等）
- [ ] `lumi init` 命令（生成 `lumi.yaml` 模板）

---

## v0.2 — 扩展能力

- [ ] Async agent 循环
- [ ] Session save/load（JSON 文件）
- [ ] Anthropic Provider（Messages API）
- [ ] 更多内置工具（`glob`、`http_get`）
- [ ] Context summarize（旧消息压缩）
- [ ] Shell sandbox 选项（`subprocess` + cwd 限制）

---

## v0.3 — 生态集成

- [ ] MCP tool adapter（接入 MCP server 的工具）
- [ ] 自定义 tool 插件（`lumi.tools` entry point）
- [ ] OpenTelemetry tracing
- [ ] 简单 eval runner（跑一组 task fixture）

---

## 里程碑时间线（建议）

```
2026-06-28  Sprint 设计文档 ✅
2026-06-29  脚手架 + config + messages
2026-06-30  LLM provider + tools
2026-07-01  Agent 循环 + events
2026-07-02  CLI + 测试 + demo 验收
2026-07-03  README + v0.1 tag
```

---

## 成功指标

| 指标 | v0.1 目标 |
|------|-----------|
| 核心代码量 | < 800 行（不含测试） |
| 外部依赖 | ≤ 5 个 |
| 测试覆盖 | config + tools + agent 核心路径 |
| 冷启动到首次 tool call | < 3s（网络正常） |
| 新 tool 接入成本 | < 20 行代码 |

---

## 开放问题

以下问题在实现阶段需确认：

1. **Streaming 是否进 v0.1？** 建议作为 v0.1.1，不阻塞 MVP
2. **Shell 默认白名单还是全开放？** 建议默认全开放 + 文档警告，生产配置白名单
3. **配置文件格式是否支持 TOML？** v0.1 仅 YAML，后续可加
4. **是否需要 `py.typed` marker？** 建议加，方便类型检查
