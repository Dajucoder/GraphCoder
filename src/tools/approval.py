"""Command approval manager (human-in-the-loop)."""

from __future__ import annotations

import asyncio
import itertools
import time
from typing import Any


class ApprovalManager:
    """Track pending shell-command approvals."""

    def __init__(self, emit: Any = None) -> None:
        self._pending: dict[str, dict[str, Any]] = {}
        self._futures: dict[str, asyncio.Future] = {}
        self._counter = itertools.count(1)
        self.emit = emit

    async def request(
        self,
        command: str,
        task_id: str,
        timeout: float = 300.0,
    ) -> bool:
        """Ask for approval; returns True if approved."""
        aid = f"ap-{next(self._counter)}"
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[aid] = {
            "id": aid,
            "command": command,
            "task_id": task_id,
            "created_at": time.time(),
            "status": "pending",
        }
        self._futures[aid] = future
        if self.emit:
            self.emit(
                "approval_request",
                {"id": aid, "command": command, "task_id": task_id},
            )
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            self._pending[aid]["status"] = "approved" if result else "rejected"
            return result
        except asyncio.TimeoutError:
            self._pending[aid]["status"] = "timeout"
            return False
        finally:
            self._futures.pop(aid, None)

    def respond(self, approval_id: str, approved: bool) -> bool:
        future = self._futures.get(approval_id)
        if future is None or future.done():
            return False
        future.set_result(approved)
        return True

    def pending(self) -> list[dict[str, Any]]:
        return list(self._pending.values())
