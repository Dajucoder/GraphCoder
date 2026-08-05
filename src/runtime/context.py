"""Workspace context helpers (AGENTS.md injection + evidence shaping)."""

from __future__ import annotations

from pathlib import Path

MAX_TOOL_RESULT_IN_CONTEXT = 8000


def load_workspace_instructions(workspace: Path, max_files: int = 3) -> str:
    """Collect AGENTS.md / CLAUDE.md instructions from the workspace root."""
    parts: list[str] = []
    for name in ("AGENTS.md", "CLAUDE.md", "agents.md"):
        path = workspace / name
        if path.exists():
            try:
                parts.append(f"# {name}\n{path.read_text(encoding='utf-8')[:12000]}")
            except OSError:
                pass
    return "\n\n".join(parts)


def shape_tool_result(result: str, max_chars: int = MAX_TOOL_RESULT_IN_CONTEXT) -> str:
    """Project a tool result for model context while keeping the evidence store full."""
    if len(result) <= max_chars:
        return result
    return result[:max_chars] + f"\n... [截断，完整结果 {len(result)} 字符已存档]"
