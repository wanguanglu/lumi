from __future__ import annotations

import logging
import time
from collections.abc import Callable

logger = logging.getLogger("lumi")


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}

    def on(self, event: str, handler: Callable) -> None:
        self._handlers.setdefault(event, []).append(handler)

    def emit(self, event: str, **kwargs) -> None:
        for handler in self._handlers.get(event, []):
            handler(**kwargs)


class LoggingHandler:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose

    def attach(self, bus: EventBus) -> None:
        bus.on("step_start", self._on_step_start)
        bus.on("step_complete", self._on_step_complete)
        bus.on("tool_start", self._on_tool_start)
        bus.on("tool_end", self._on_tool_end)
        bus.on("server_tool_start", self._on_server_tool_start)
        bus.on("server_tool_end", self._on_server_tool_end)
        bus.on("agent_end", self._on_agent_end)
        bus.on("error", self._on_error)

    def _on_step_start(self, step: int, max_steps: int, **_: object) -> None:
        if self.verbose:
            logger.info("step %d/%d", step + 1, max_steps)

    def _on_step_complete(self, step: int, final: bool, **_: object) -> None:
        if self.verbose and final:
            logger.info("done at step %d", step + 1)

    def _on_tool_start(self, name: str, arguments: dict, **_: object) -> None:
        if self.verbose:
            logger.info("→ tool: %s(%s)", name, arguments)

    def _on_tool_end(self, name: str, result: str, duration_ms: float, **_: object) -> None:
        if self.verbose:
            logger.info("← tool: %s (%d bytes, %.0fms)", name, len(result), duration_ms)

    def _on_server_tool_start(self, name: str, type: str, **_: object) -> None:
        if self.verbose:
            logger.info("→ server: %s (%s)", name, type)

    def _on_server_tool_end(self, name: str, results_count: int, **_: object) -> None:
        if self.verbose:
            logger.info("← server: %s (%d results)", name, results_count)

    def _on_agent_end(self, result: str, steps: int, **_: object) -> None:
        if self.verbose:
            logger.info("✓ completed in %d steps", steps)

    def _on_error(self, error: Exception, **_: object) -> None:
        logger.error("error: %s", error)


def measure_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
