"""Agent engine tests (own provider + tool loop + permission gate)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.providers.base import ProviderConfig, ToolCall
from src.runtime.approvals import ApprovalHub
from src.runtime.engine import AgentEngine, TurnResult
from src.runtime.events import EventBus
from src.runtime.permission import ALLOW, DENY, PermissionEngine


class FakeProvider:
    """Scripted provider: tool_call first, then text."""

    def __init__(self, tool: ToolCall | None, text: str) -> None:
        self.tool = tool
        self.text = text
        self.rounds = 0

    async def stream(self, messages, tools=None):
        self.rounds += 1
        if self.tool is not None and self.rounds == 1:
            yield ("tool_call", self.tool)
        else:
            for ch in self.text:
                yield ("text", ch)
        yield ("done", self.text)

    async def complete(self, messages, tools=None):
        return self.text, []


def _engine(tmp_path: Path, tool: ToolCall | None = None, text: str = "完成") -> AgentEngine:
    cfg = ProviderConfig(
        name="Test",
        kind="openai-compatible",
        base_url="http://127.0.0.1:9/v1",
        api_key="k",
        model="m",
    )
    engine = AgentEngine(
        provider_config=cfg,
        bus=EventBus(),
        approvals=ApprovalHub(),
        options={"max_iterations": 5},
        workspace=tmp_path,
    )
    engine.provider = FakeProvider(tool, text)  # type: ignore[assignment]
    return engine


def test_engine_permission_for() -> None:
    engine = _engine(Path("/tmp"))
    perm = PermissionEngine()
    perm.add_rule("command", "git status*", ALLOW)
    perm.add_rule("command", "rm *", DENY)
    engine.permission = perm
    assert engine._permission_for("run_shell", {"command": "git status"}) == ALLOW
    assert engine._permission_for("run_shell", {"command": "rm -rf x"}) == DENY
    assert engine._permission_for("write_file", {"path": "/a/b.txt"}) == "ask"  # 无规则默认询问


def test_engine_tool_loop_writes_file(tmp_path: Path) -> None:
    events: list[tuple[str, dict]] = []
    bus = EventBus(listener=lambda t, p: events.append((t, p)))
    cfg = ProviderConfig(name="T", kind="openai-compatible", base_url="http://127.0.0.1:9/v1", api_key="k", model="m")
    engine = AgentEngine(provider_config=cfg, bus=bus, approvals=ApprovalHub(), options={}, workspace=tmp_path)
    perm = PermissionEngine()
    perm.add_rule("dir", str(tmp_path), ALLOW)
    engine.permission = perm
    tool = ToolCall(id="c1", name="write_file", arguments={"path": "out.txt", "content": "hi"})
    engine.provider = FakeProvider(tool, "已写入")  # type: ignore[assignment]

    async def run() -> TurnResult:
        result = await engine.run(thread_id="t", turn_id="turn", user_message="写文件")
        return result

    result = asyncio.run(run())
    assert result.ok
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "hi"
    kinds = [e[1].get("kind") for e in events]
    assert "tool_call" in kinds
    assert "agent_message" in kinds
