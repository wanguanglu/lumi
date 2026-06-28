# Lumi Sprint — 2026-06-28

> 极简 LLM Agent Harness · Python · OpenAI-compatible Provider

## Sprint 目标

搭建 **lumi** 的项目设计基线，明确 v0.1 的范围、架构与配置规范，为后续实现提供单一事实来源（single source of truth）。

**v0.1 交付标准：** 通过 CLI 运行一个完整的 ReAct agent 循环，使用配置文件指定 OpenAI 兼容 API，内置 2–3 个文件/Shell 工具，完成端到端 demo 任务。

## 设计原则

1. **Explicit over magic** — agent 循环、工具调用路径清晰可见，便于调试
2. **Provider agnostic** — v0.1 只实现 OpenAI-compatible adapter，但接口预留扩展
3. **Tools are first-class** — 扩展能力 = 注册新 tool，不改 agent 核心
4. **Fail gracefully** — 工具失败以 tool message 回传 LLM，而非直接 crash
5. **Minimal by default** — 无明确场景的功能一律不进 v0.1

## 文档索引

| 文档 | 内容 |
|------|------|
| [architecture.md](./architecture.md) | 系统架构、模块划分、Agent 主循环 |
| [configuration.md](./configuration.md) | 配置文件格式、Provider 配置、环境变量 |
| [modules.md](./modules.md) | 各模块 API 设计与数据结构 |
| [roadmap.md](./roadmap.md) | v0.1 范围、里程碑、明确不做的事 |

## 技术选型

| 项 | 选择 | 理由 |
|----|------|------|
| 语言 | Python ≥ 3.11 | 生态成熟、tool calling 支持好 |
| 包管理 | `pyproject.toml` + uv/pip | 标准现代 Python 项目结构 |
| HTTP 客户端 | `httpx` | 轻量、支持 async（v0.2 预留） |
| 配置解析 | `pyyaml` | 人类可读、支持注释 |
| CLI | `typer` | 类型友好、自动生成 help |
| LLM SDK | 不依赖官方 SDK，直接调 REST | 减少依赖、兼容任意 OpenAI-compatible 端点 |

## 项目结构（目标）

```
lumi/
├── pyproject.toml
├── README.md
├── lumi.yaml                  # 示例配置（不入库 secrets）
├── lumi/
│   ├── __init__.py
│   ├── agent.py               # ReAct 主循环
│   ├── config.py              # 配置加载与校验
│   ├── messages.py            # 消息模型
│   ├── events.py              # Hook / 事件系统
│   ├── cli.py                 # CLI 入口
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py            # LLM 抽象接口
│   │   └── openai.py          # OpenAI-compatible 实现
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── registry.py        # 工具注册表
│   │   ├── filesystem.py      # read_file / write_file
│   │   └── shell.py           # run_shell
│   └── prompts/
│       └── default.txt        # 默认 system prompt
└── tests/
    ├── test_agent.py
    ├── test_config.py
    └── test_tools.py
```

## 快速预览：一次完整运行

```bash
# 安装
pip install -e .

# 配置（见 configuration.md）
cp lumi.yaml.example lumi.yaml
export OPENAI_API_KEY=sk-...

# 单次任务
lumi run "读取 README.md，总结项目结构，写入 outline.md"

# 交互模式
lumi chat
```

## 相关决策记录

- **为何不用 LangChain？** 目标是可嵌入的轻量运行时，而非通用框架
- **为何配置文件而非纯环境变量？** Provider 参数（base_url、model 等）组合多，文件更易管理；密钥仍走环境变量
- **为何 CLI-first？** 验证 harness 最快路径；Web UI 不在 v0.1 范围
