"""File-system tools for the coding agent."""

from __future__ import annotations

import os
from pathlib import Path

from src.tools.base import Tool, ToolContext, safe_join


async def _read_file(args: dict, ctx: ToolContext) -> str:
    try:
        path = safe_join(ctx.workspace, args.get("path", ""))
    except ValueError as exc:
        return f"错误: {exc}"
    if not path.exists():
        return f"错误: 文件不存在: {path}"
    if path.is_dir():
        return f"错误: 这是一个目录: {path}"
    max_chars = int(args.get("max_chars", 30000))
    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n... [已截断，共 {len(content)} 字符]"
    return content


async def _write_file(args: dict, ctx: ToolContext) -> str:
    try:
        path = safe_join(ctx.workspace, args.get("path", ""))
    except ValueError as exc:
        return f"错误: {exc}"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = args.get("content", "")
    path.write_text(content, encoding="utf-8")
    return f"已写入 {path.relative_to(ctx.workspace)} ({len(content)} 字符)"


async def _list_files(args: dict, ctx: ToolContext) -> str:
    try:
        root = safe_join(ctx.workspace, args.get("path", "."))
    except ValueError as exc:
        return f"错误: {exc}"
    if not root.exists():
        return f"错误: 路径不存在: {root}"
    depth = int(args.get("depth", 2))
    root = root.resolve()
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".mypy_cache", ".ruff_cache", ".pytest_cache", "dist", "build", ".graphcoder"}
    lines: list[str] = []

    def walk(directory: Path, prefix: str, level: int) -> None:
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return
        for entry in entries:
            if entry.name in skip:
                continue
            if entry.name.startswith(".") and entry.is_dir():
                continue
            marker = "📄" if entry.is_file() else "📁"
            lines.append(f"{prefix}{marker} {entry.name}")
            if entry.is_dir() and level < depth:
                walk(entry, prefix + "  ", level + 1)

    walk(root, "", 0)
    if not lines:
        return "(空目录)"
    return "\n".join(lines)


async def _search_files(args: dict, ctx: ToolContext) -> str:
    import re

    pattern = args.get("pattern", "")
    path = args.get("path", ".")
    if not pattern:
        return "错误: 需要 pattern 参数"
    try:
        root = safe_join(ctx.workspace, path)
    except ValueError as exc:
        return f"错误: {exc}"
    regex = re.compile(pattern)
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".graphcoder"}
    results: list[str] = []
    max_results = int(args.get("max_results", 50))
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        for fname in filenames:
            if any(fname.endswith(ext) for ext in (".pyc", ".png", ".jpg", ".gif", ".ico", ".lock")):
                continue
            full = Path(dirpath) / fname
            try:
                rel = full.relative_to(ctx.workspace)
                for lineno, line in enumerate(full.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if regex.search(line):
                        results.append(f"{rel}:{lineno}: {line.strip()[:200]}")
                        if len(results) >= max_results:
                            return "\n".join(results) + f"\n... (已达上限 {max_results})"
            except (OSError, UnicodeDecodeError):
                continue
    return "\n".join(results) if results else f"未找到匹配 '{pattern}' 的内容"


async def _apply_patch(args: dict, ctx: ToolContext) -> str:
    """Apply a simple unified diff patch to a file."""
    import difflib

    try:
        path = safe_join(ctx.workspace, args.get("path", ""))
    except ValueError as exc:
        return f"错误: {exc}"
    if not path.exists():
        return f"错误: 文件不存在: {path}"
    old = path.read_text(encoding="utf-8")
    new = args.get("new_content", "")
    if not new:
        return "错误: 需要 new_content（完整新文件内容）"
    diff = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm=""))
    path.write_text(new, encoding="utf-8")
    return f"补丁已应用:\n{diff}"


def file_tools() -> list[Tool]:
    return [
        Tool(
            name="read_file",
            description="读取工作区内指定文件的文本内容。路径相对于工作区根目录。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对路径，如 src/main.py"},
                    "max_chars": {"type": "integer", "description": "最多读取字符数", "default": 30000},
                },
                "required": ["path"],
            },
            handler=_read_file,
        ),
        Tool(
            name="write_file",
            description="创建或覆盖工作区内的一个文件。会自动创建父目录。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对路径"},
                    "content": {"type": "string", "description": "完整文件内容"},
                },
                "required": ["path", "content"],
            },
            handler=_write_file,
        ),
        Tool(
            name="list_files",
            description="列出工作区目录树（默认深度 2，跳过 node_modules/.git 等）。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对目录", "default": "."},
                    "depth": {"type": "integer", "description": "递归深度", "default": 2},
                },
                "required": [],
            },
            handler=_list_files,
        ),
        Tool(
            name="search_files",
            description="在工作区中按正则表达式搜索文件内容，返回 文件:行号:内容。",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "正则表达式"},
                    "path": {"type": "string", "description": "搜索目录", "default": "."},
                    "max_results": {"type": "integer", "description": "结果上限", "default": 50},
                },
                "required": ["pattern"],
            },
            handler=_search_files,
        ),
        Tool(
            name="apply_patch",
            description="用完整新内容替换文件（适用于修改代码）。给出 path 与 new_content。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对路径"},
                    "new_content": {"type": "string", "description": "修改后的完整文件内容"},
                },
                "required": ["path", "new_content"],
            },
            handler=_apply_patch,
        ),
    ]
