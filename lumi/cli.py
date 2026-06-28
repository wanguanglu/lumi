from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.markdown import Markdown

from lumi.agent import Agent, MaxStepsExceeded
from lumi.config import ConfigError, load_config, mask_api_key
from lumi.events import EventBus, LoggingHandler
from lumi.llm.base import LLMError
from lumi.llm import create_llm
from lumi.prompts_loader import load_prompt
from lumi.tools import create_tool_registry

app = typer.Typer(
    name="lumi",
    help="A minimal LLM agent harness",
    no_args_is_help=True,
)
config_app = typer.Typer(name="config", help="Configuration commands")
tools_app = typer.Typer(name="tools", help="Tool management")
app.add_typer(config_app)
app.add_typer(tools_app)

console = Console()


def _format_llm_error(error: LLMError) -> str:
    message = str(error)
    if error.body:
        message = f"{message}\n{error.body}"
    return message


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[lumi] %(message)s",
    )


def _build_agent(config_path: Path | None, verbose: bool) -> Agent:
    config = load_config(config_path)
    _setup_logging(config.logging.level if verbose else "WARNING")

    events = EventBus()
    if verbose:
        LoggingHandler(verbose=True).attach(events)

    return Agent(
        llm=create_llm(config.llm),
        tools=create_tool_registry(config.tools),
        config=config.agent,
        system_prompt=load_prompt(config.agent.system_prompt),
        events=events,
    )


def _config_to_dict(config_path: Path | None) -> dict:
    config = load_config(config_path)
    return {
        "llm": {
            "provider": config.llm.provider,
            "base_url": config.llm.base_url,
            "api_key": mask_api_key(config.llm.api_key),
            "model": config.llm.model,
            "temperature": config.llm.temperature,
            "max_tokens": config.llm.max_tokens,
            "timeout": config.llm.timeout,
        },
        "agent": {
            "max_steps": config.agent.max_steps,
            "system_prompt": config.agent.system_prompt,
            "context_window": config.agent.context_window,
        },
        "tools": {
            "enabled": config.tools.enabled,
            "shell": {
                "timeout": config.tools.shell_timeout,
                "allowed_commands": config.tools.shell_allowed_commands,
            },
        },
        "logging": {
            "level": config.logging.level,
            "format": config.logging.format,
        },
    }


@app.command()
def run(
    task: Annotated[str, typer.Argument(help="Task for the agent to execute")],
    config: Annotated[Path | None, typer.Option("--config", help="Config file path")] = None,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Verbose output")] = False,
) -> None:
    """Run a single agent task."""
    try:
        agent = _build_agent(config, verbose)
        result = agent.run(task)
        console.print(Markdown(result))
    except ConfigError as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(1) from e
    except MaxStepsExceeded as e:
        console.print(f"[red]Max steps exceeded ({e.max_steps})[/red]")
        raise typer.Exit(1) from e
    except LLMError as e:
        console.print(f"[red]LLM error:[/red] {_format_llm_error(e)}")
        raise typer.Exit(1) from e
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130) from None


@app.command()
def chat(
    config: Annotated[Path | None, typer.Option("--config", help="Config file path")] = None,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Verbose output")] = False,
) -> None:
    """Interactive chat mode."""
    try:
        agent = _build_agent(config, verbose)
    except ConfigError as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(1) from e

    console.print("[dim]Lumi chat (type 'exit' or 'quit' to leave)[/dim]")

    while True:
        try:
            user_input = console.input("[bold blue]you>[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            console.print("[dim]Goodbye[/dim]")
            break

        try:
            result = agent.chat(user_input)
            console.print("[bold green]lumi>[/bold green]", Markdown(result))
        except MaxStepsExceeded as e:
            console.print(f"[red]Max steps exceeded ({e.max_steps})[/red]")
        except LLMError as e:
            console.print(f"[red]LLM error:[/red] {_format_llm_error(e)}")


@config_app.command("show")
def config_show(
    config: Annotated[Path | None, typer.Option("--config", help="Config file path")] = None,
) -> None:
    """Show current effective configuration (secrets masked)."""
    try:
        data = _config_to_dict(config)
        console.print(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    except ConfigError as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(1) from e


@config_app.command("validate")
def config_validate(
    config: Annotated[Path | None, typer.Option("--config", help="Config file path")] = None,
) -> None:
    """Validate configuration file."""
    try:
        load_config(config)
        console.print("[green]Configuration is valid[/green]")
    except ConfigError as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(1) from e


@tools_app.command("list")
def tools_list(
    config: Annotated[Path | None, typer.Option("--config", help="Config file path")] = None,
) -> None:
    """List enabled tools."""
    try:
        config_obj = load_config(config)
        registry = create_tool_registry(config_obj.tools)
        for name in registry.names:
            tool = registry.get(name)
            if tool:
                console.print(f"[bold]{name}[/bold]: {tool.description}")
    except ConfigError as e:
        console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(1) from e


def main() -> None:
    app()


if __name__ == "__main__":
    main()
