"""GraphCoder Textual TUI (Codex-style fullscreen conversation interface)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Static

from src.cli.rpc_client import RpcClient

AGENT_COLOR = "magenta"
USER_COLOR = "cyan"
OK_COLOR = "green"
ERR_COLOR = "red"


class Conversation(Container):
    """Scrollable conversation log with item rendering."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._stream_item: Static | None = None
        self._stream_text = ""

    def add_user(self, text: str) -> None:
        self.mount(Static(f"[{USER_COLOR}]{text}[/]", classes="msg user"), before=None)
        self._scroll_end()

    def add_agent_header(self, role: str = "assistant") -> None:
        self._stream_item = Static(f"[{AGENT_COLOR}]▍{role}[/]", classes="msg agent")
        self.mount(self._stream_item)
        self._scroll_end()

    def stream_delta(self, delta: str) -> None:
        if self._stream_item is None:
            self.add_agent_header()
        assert self._stream_item is not None
        self._stream_text += delta
        self._stream_item.update(f"[{AGENT_COLOR}]{self._stream_text}[/]")
        self._scroll_end()

    def finish_stream(self, final: str = "") -> None:
        if final and self._stream_item is not None:
            self._stream_item.update(f"[{AGENT_COLOR}]{final}[/]")
        self._stream_item = None
        self._stream_text = ""
        self._scroll_end()

    def add_tool(self, name: str, arguments: dict[str, Any]) -> None:
        self.mount(Static(f"[bold cyan]🔧 {name}[/] {arguments}", classes="tool"))
        self._scroll_end()

    def add_status(self, text: str) -> None:
        self.mount(Static(f"[dim]{text}[/]", classes="status"))
        self._scroll_end()

    def add_error(self, text: str) -> None:
        self.mount(Static(f"[{ERR_COLOR}]✗ {text}[/]", classes="msg error"))
        self._scroll_end()

    def _scroll_end(self) -> None:
        try:
            self.call_after_refresh(self._scroll_bottom)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).debug("滚动调度失败: %s", exc)

    def _scroll_bottom(self) -> None:
        try:
            self.scroll_end(animate=False)
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).debug("滚动失败: %s", exc)


class ApprovalBar(Horizontal):
    """Inline approval prompt with Allow / Deny buttons."""

    def __init__(self, approval_id: str, reason: str, target: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.approval_id = approval_id
        self.reason = reason
        self.target = target

    def compose(self) -> ComposeResult:
        yield Static(f"[yellow]⏸ 审批: {self.target}[/] {self.reason}", id="approval-text")
        yield Button("允许", variant="success", id="approve-btn")
        yield Button("拒绝", variant="error", id="deny-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        approved = event.button.id == "approve-btn"
        asyncio.create_task(self._respond(approved))

    async def _respond(self, approved: bool) -> None:
        app = self.app
        assert isinstance(app, GraphCoderTui)
        await app.rpc.request("approvals/respond", {"id": self.approval_id, "approved": approved})
        self.remove()


class GraphCoderTui(App[None]):
    """Fullscreen GraphCoder TUI."""

    CSS = """
    Screen { background: #0d1117; }
    #conversation { height: 1fr; padding: 0 2; }
    #approval-area { height: auto; padding: 0 2 1 2; }
    #composer { dock: bottom; height: auto; padding: 0 2 1 2; }
    #input { width: 1fr; }
    #send { width: 12; margin-left: 1; }
    .msg { margin: 1 0 0 0; }
    .tool { margin: 0 0 0 1; color: #8b949e; }
    .status { color: #8b949e; }
    """

    mode: reactive[str] = reactive("chat")

    def __init__(
        self,
        workspace: Path | None = None,
        home: Path | None = None,
        thread_id: str | None = None,
    ) -> None:
        super().__init__()
        self.workspace = workspace or Path.cwd()
        self.home = home
        self.rpc = RpcClient(workspace=self.workspace, home=self.home, on_notification=self._on_notification)
        self.thread_id = thread_id or ""
        self._turn_id = ""
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Conversation(id="conversation")
        yield Container(id="approval-area")
        yield Footer()
        with Container(id="composer"):
            yield Input(placeholder="输入消息，回车发送（/help 查看命令）", id="input")
            yield Button("发送", id="send")

    # ------------------------------------------------------------------
    async def on_mount(self) -> None:
        self.title = f"GraphCoder — {self.workspace}"
        self.sub_title = "连接运行时…"
        await self.rpc.start()
        info = await self.rpc.request("initialize")
        model = info.get("defaults", {}).get("model", "")
        self.sub_title = f"模型: {model} · 模式: {self.mode} · /help"
        if not self.thread_id:
            threads = await self.rpc.request("threads/list")
            if threads.get("threads"):
                self.thread_id = threads["threads"][0]["id"]
            else:
                created = await self.rpc.request("threads/create", {"title": "TUI 会话"})
                self.thread_id = created["id"]
        data = await self.rpc.request("threads/get", {"thread_id": self.thread_id})
        for ev in data.get("events", []):
            self._render_event(ev)

    async def on_unmount(self) -> None:
        await self.rpc.close()

    # ------------------------------------------------------------------
    def watch_mode(self, old: str, new: str) -> None:
        self.sub_title = f"模型: {self.sub_title} · 模式: {new} · /help"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        asyncio.create_task(self._submit(event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send":
            input_widget = self.query_one("#input", Input)
            asyncio.create_task(self._submit(input_widget.value))

    async def _submit(self, raw: str) -> None:
        text = raw.strip()
        if not text or self._busy:
            return
        input_widget = self.query_one("#input", Input)
        input_widget.value = ""
        if text.startswith("/"):
            await self._slash(text)
            return
        self._busy = True
        conv = self.query_one("#conversation", Conversation)
        conv.add_user(text)
        conv.add_status(f"◐ 运行中（{self.mode} 模式）…")
        try:
            result = await self.rpc.request(
                "threads/prompt",
                {"thread_id": self.thread_id, "content": text, "mode": self.mode},
            )
            self._turn_id = result["task"]["id"]
        except Exception as exc:  # noqa: BLE001
            conv.add_error(str(exc))
        finally:
            self._busy = False

    async def _slash(self, cmd: str) -> None:
        conv = self.query_one("#conversation", Conversation)
        parts = cmd.split(maxsplit=1)
        name = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        if name in ("/exit", "/quit"):
            self.exit()
        elif name == "/help":
            conv.add_status(
                "/new 新会话 · /graph 构建模式 · /chat 聊天模式 · /model <id> 切换模型 · "
                "/permission allow|ask|deny <命令> · /resume 续跑 · /exit 退出"
            )
        elif name == "/new":
            created = await self.rpc.request("threads/create", {"title": "TUI 会话"})
            self.thread_id = created["id"]
            conv.add_status(f"新会话 {self.thread_id}")
        elif name == "/graph":
            self.mode = "build"
            conv.add_status("已切换到构建模式（PM→架构→编码→审查→QA）")
        elif name == "/chat":
            self.mode = "chat"
            conv.add_status("已切换到聊天模式")
        elif name == "/model":
            models = await self.rpc.request("models/list")
            target = arg or ""
            for m in models.get("models", []):
                if m["id"] == target:
                    await self.rpc.request("settings/set", {"options": {"active_provider": m["id"]}})
                    self.sub_title = f"模型: {m['model'] or m['name']} · 模式: {self.mode}"
                    conv.add_status(f"已切换模型: {m['name']}")
                    return
            conv.add_status("可用模型: " + ", ".join(m["id"] for m in models.get("models", [])))
        elif name == "/permission":
            action, _, pattern = arg.partition(" ")
            if action in ("allow", "ask", "deny") and pattern:
                await self.rpc.request(
                    "permissions/add",
                    {"kind": "command", "pattern": pattern, "action": action},
                )
                conv.add_status(f"已添加策略: {action} {pattern}")
            else:
                conv.add_status("用法: /permission allow|ask|deny <命令模式>")
        elif name == "/resume":
            if self._turn_id:
                await self.rpc.request("threads/resume", {"task_id": self._turn_id})
                conv.add_status("已发起续跑")
            else:
                conv.add_status("当前没有可续跑的任务")
        else:
            conv.add_status(f"未知命令: {name}（/help 查看帮助）")

    # ------------------------------------------------------------------
    async def _on_notification(self, method: str, params: dict[str, Any]) -> None:
        conv = self.query_one("#conversation", Conversation)
        if method == "item/started":
            kind = params.get("kind")
            if kind == "user_message":
                pass
            elif kind == "tool_call":
                conv.add_tool(params.get("name", "tool"), params.get("arguments") or {})
            elif kind == "agent_message":
                conv.add_agent_header(params.get("role", "assistant"))
        elif method == "item/delta":
            conv.stream_delta(params.get("delta", ""))
        elif method == "item/completed":
            payload = params.get("payload") or {}
            if params.get("kind") == "agent_message":
                conv.finish_stream(payload.get("content", ""))
        elif method == "approval/requested":
            area = self.query_one("#approval-area")
            area.mount(ApprovalBar(params["id"], params.get("reason", ""), params.get("target", "")))
        elif method == "turn/completed":
            status = params.get("status")
            color = OK_COLOR if status == "completed" else ERR_COLOR
            conv.add_status(f"[{color}]◉ 回合结束: {status}[/]")
            self._turn_id = ""
        elif method == "error":
            conv.add_error(params.get("message", ""))

    def _render_event(self, ev: dict[str, Any]) -> None:
        conv = self.query_one("#conversation", Conversation)
        etype = ev.get("type")
        outer = ev.get("payload") or {}
        inner = outer.get("payload") or {}
        kind = outer.get("kind")
        if etype == "item/completed":
            if kind == "user_message":
                conv.add_user(inner.get("content", ""))
            elif kind == "agent_message" and inner.get("content"):
                conv.add_agent_header(outer.get("role", "assistant"))
                conv.finish_stream(inner["content"])
        elif etype == "item/started" and kind == "tool_call":
            conv.add_tool(outer.get("name", "tool"), outer.get("arguments") or {})


def run_tui(workspace: Path | None = None, home: Path | None = None, thread_id: str | None = None) -> None:
    GraphCoderTui(workspace=workspace, home=home, thread_id=thread_id).run()
