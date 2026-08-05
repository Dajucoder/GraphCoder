"""Tool definitions and execution context."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.providers.base import ToolSpec

ToolHandler = Callable[[dict[str, Any], "ToolContext"], Awaitable[str]]


@dataclass
class ToolContext:
    """Everything a tool needs at runtime."""

    workspace: Path
    task_id: str = ""
    session_id: str = ""
    emit: Callable[[str, dict[str, Any]], None] | None = None
    approvals: Any = None
    shell_approval: str = "ask"  # ask | auto | never


@dataclass
class Tool:
    """A registered tool with schema + async handler."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    require_approval: bool = False

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )

    def emit(self, ctx: ToolContext, kind: str, payload: dict[str, Any]) -> None:
        if ctx.emit:
            ctx.emit(kind, {"task_id": ctx.task_id, **payload})


def safe_join(workspace: Path, *parts: str) -> Path:
    """Resolve a path and ensure it stays inside the workspace."""
    root = workspace.resolve()
    target = root.joinpath(*parts).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"路径越界，禁止访问 workspace 之外: {target}")
    return target
