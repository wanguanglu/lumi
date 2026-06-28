# Lumi

A minimal LLM agent harness in Python.

Lumi runs a ReAct loop: the LLM can call tools (read/write files, run shell commands) until the task is complete.

## Install

```bash
pip install -e .
# or with dev dependencies
pip install -e ".[dev]"
```

## Configure

Copy the example config and set your API key:

```bash
cp lumi.yaml.example lumi.yaml
export OPENAI_API_KEY=sk-...
```

Lumi uses any **OpenAI-compatible** API. Set `provider` to the vendor name:

```yaml
# DeepSeek
provider: deepseek
base_url: https://api.deepseek.com/v1   # optional, auto-filled for deepseek
model: deepseek-chat

# OpenAI
provider: openai
model: gpt-4o

# Ollama (local)
provider: ollama
model: llama3.1
```

Config lookup order: `--config` → `LUMI_CONFIG` → `./lumi.yaml` → `~/.config/lumi/lumi.yaml`

## Usage

```bash
# Single task
lumi run "读取 README.md 并总结内容"

# Interactive chat
lumi chat

# List tools
lumi tools list

# Validate config
lumi config validate
```

Verbose mode shows tool calls and steps:

```bash
lumi -v run "列出当前目录的 Python 文件"
```

## Built-in Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents (max 100KB) |
| `write_file` | Write file, auto-create directories |
| `run_shell` | Execute shell command |

## Development

```bash
pytest
ruff check lumi tests
```

## License

MIT
