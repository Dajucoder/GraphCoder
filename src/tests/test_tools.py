"""Tool layer tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.tools.base import Tool, ToolContext, safe_join
from src.tools.files import file_tools
from src.tools.registry import all_tools


def _tools_by_name() -> dict[str, Tool]:
    return {t.name: t for t in file_tools()}


def test_file_tools_registered() -> None:
    names = {t.name for t in all_tools()}
    assert {"read_file", "write_file", "list_files", "search_files", "apply_patch"} <= names


def test_safe_join_rejects_escape(tmp_path: Path) -> None:
    try:
        safe_join(tmp_path, "../escape.txt")
        assert False, "should raise"
    except ValueError:
        pass


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    async def run() -> None:
        ctx = ToolContext(workspace=tmp_path)
        tools = _tools_by_name()
        write = tools["write_file"].handler
        read = tools["read_file"].handler
        result = await write({"path": "hello.txt", "content": "你好 world"}, ctx)
        assert "已写入" in result
        content = await read({"path": "hello.txt"}, ctx)
        assert content == "你好 world"

    asyncio.run(run())


def test_read_missing_file(tmp_path: Path) -> None:
    async def run() -> None:
        ctx = ToolContext(workspace=tmp_path)
        result = await _tools_by_name()["read_file"].handler({"path": "nope.txt"}, ctx)
        assert "不存在" in result

    asyncio.run(run())


def test_search_finds_pattern(tmp_path: Path) -> None:
    async def run() -> None:
        (tmp_path / "app.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
        ctx = ToolContext(workspace=tmp_path)
        result = await _tools_by_name()["search_files"].handler(
            {"pattern": "def hello"}, ctx
        )
        assert "app.py:1" in result

    asyncio.run(run())


def test_write_rejects_path_escape(tmp_path: Path) -> None:
    async def run() -> None:
        ctx = ToolContext(workspace=tmp_path)
        result = await _tools_by_name()["write_file"].handler(
            {"path": "../evil.txt", "content": "x"}, ctx
        )
        assert "越界" in result
        assert not (tmp_path.parent / "evil.txt").exists()

    asyncio.run(run())
