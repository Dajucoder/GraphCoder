"""Thread (session) manager: lifecycle, turns, durable tasks."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from src.runtime.context import load_workspace_instructions
from src.runtime.engine import AgentEngine
from src.runtime.events import EventBus
from src.runtime.orchestrator import run_build_pipeline
from src.storage.sqlite_store import SqliteStore


class ThreadManager:
    """Coordinates thread lifecycle and turn execution over the SQLite store."""

    def __init__(
        self,
        store: SqliteStore,
        adapter: AgentEngine,
        bus: EventBus,
        workspace: Path,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.bus = bus
        self.workspace = workspace
        self.options = options or {}
        self._running: dict[str, asyncio.Task] = {}

    # ---------------- thread lifecycle ----------------
    async def create_thread(self, title: str = "新会话", parent_id: str | None = None, branch_point: str | None = None):
        return await self.store.create_session(title, parent_id, branch_point)

    async def list_threads(self, include_archived: bool = False):
        return await self.store.list_sessions(include_archived)

    async def get_thread(self, thread_id: str):
        return await self.store.get_session(thread_id)

    async def rename_thread(self, thread_id: str, title: str) -> bool:
        return await self.store.rename_session(thread_id, title)

    async def archive_thread(self, thread_id: str, archived: bool = True) -> bool:
        return await self.store.archive_session(thread_id, archived)

    async def fork_thread(self, thread_id: str, branch_point: str | None = None):
        return await self.store.fork_session(thread_id, branch_point)

    async def delete_thread(self, thread_id: str) -> bool:
        return await self.store.delete_session(thread_id)

    async def thread_events(self, thread_id: str, after_seq: int = 0):
        return await self.store.events(thread_id, after_seq)

    # ---------------- turns ----------------
    async def prompt(self, thread_id: str, content: str, mode: str = "chat", budgets: dict[str, Any] | None = None):
        thread = await self.store.get_session(thread_id)
        if thread is None:
            raise KeyError(f"会话不存在: {thread_id}")
        task = await self.store.create_task(thread_id, mode, content, budgets)
        self.bus.emit("thread/started", thread_id=thread_id)
        self.bus.emit("turn/started", thread_id=thread_id, turn_id=task["id"], input=content)
        user_item = f"item-{uuid.uuid4().hex[:10]}"
        self.bus.emit(
            "item/started",
            thread_id=thread_id,
            turn_id=task["id"],
            item_id=user_item,
            kind="user_message",
        )
        self.bus.emit(
            "item/completed",
            thread_id=thread_id,
            turn_id=task["id"],
            item_id=user_item,
            kind="user_message",
            payload={"content": content},
        )
        runner = asyncio.create_task(self._run_turn(thread_id, task))
        self._running[task["id"]] = runner
        return task

    async def _run_turn(self, thread_id: str, task: dict[str, Any]) -> None:
        tid = task["id"]
        try:
            await self.store.update_task(tid, status="running")
            if task["mode"] == "build":
                instructions = load_workspace_instructions(self.workspace)
                result = await run_build_pipeline(
                    self.adapter,
                    thread_id=thread_id,
                    turn_id=tid,
                    request=task["content"],
                    workspace_instructions=instructions,
                    max_attempts=int(self.options.get("max_attempts", 3)),
                )
                text = (
                    f"## QA 结论\n{result['qa_result']}\n\n"
                    f"## 实现摘要\n{result['implementation'][:2000]}"
                )
                ok = result["qa_pass"]
            else:
                history = await self._history_messages(thread_id)
                turn = await self.adapter.run(
                    thread_id=thread_id,
                    turn_id=tid,
                    user_message=task["content"],
                    conversation_history=history,
                    role="assistant",
                    budgets=task.get("budgets") or {},
                )
                text = turn.text
                ok = turn.ok
            if self.adapter.usage:
                await self.store.add_usage(
                    {
                        "session_id": thread_id,
                        "task_id": tid,
                        "provider": getattr(self.adapter.cfg, "name", ""),
                        "model": getattr(self.adapter.cfg, "model", ""),
                        "input_tokens": self.adapter.usage.get("input_tokens", 0),
                        "output_tokens": self.adapter.usage.get("output_tokens", 0),
                    }
                )
            await self.store.update_task(tid, status="completed" if ok else "error")
            self.bus.emit(
                "turn/completed",
                thread_id=thread_id,
                turn_id=tid,
                status="completed" if ok else "error",
                content=text,
            )
        except Exception as exc:  # noqa: BLE001
            await self.store.update_task(tid, status="error")
            self.bus.emit("error", thread_id=thread_id, turn_id=tid, message=str(exc))
            self.bus.emit(
                "turn/completed",
                thread_id=thread_id,
                turn_id=tid,
                status="error",
                content=str(exc),
            )
        finally:
            self._running.pop(tid, None)

    async def _history_messages(self, thread_id: str) -> list[dict[str, Any]]:
        """Project completed message items into conversation history."""
        history: list[dict[str, Any]] = []
        for ev in await self.store.events(thread_id):
            if ev["type"] == "item/completed":
                payload = ev["payload"]
                if payload.get("kind") == "user_message":
                    history.append({"role": "user", "content": payload.get("content", "")})
                elif payload.get("kind") == "agent_message" and payload.get("content"):
                    history.append({"role": "assistant", "content": payload["content"]})
        return history

    async def stop(self, task_id: str) -> bool:
        runner = self._running.get(task_id)
        if runner is None:
            return False
        runner.cancel()
        await self.store.update_task(task_id, status="cancelled")
        return True
