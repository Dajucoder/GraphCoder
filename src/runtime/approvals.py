"""Async approval hub: pauses a turn until the client responds."""

from __future__ import annotations

import asyncio
import itertools
import time
from typing import Any

from src.runtime.events import EventBus


class ApprovalHub:
    """Pending-approval registry used by the agent engine (async)."""

    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus or EventBus()
        self._futures: dict[str, asyncio.Future] = {}
        self._pending: dict[str, dict[str, Any]] = {}
        self._counter = itertools.count(1)

    async def request(
        self,
        *,
        kind: str,
        target: str,
        reason: str,
        rule_key: str,
        task_id: str = "",
        timeout: float = 300.0,
    ) -> tuple[bool, str]:
        """Emit approval/requested and wait. Returns (approved, scope)."""
        aid = f"ap-{next(self._counter)}"
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._futures[aid] = future
        self._pending[aid] = {
            "id": aid,
            "kind": kind,
            "target": target,
            "reason": reason,
            "rule_key": rule_key,
            "task_id": task_id,
            "ts": time.time(),
        }
        self.bus.emit(
            "approval/requested",
            id=aid,
            kind=kind,
            target=target,
            reason=reason,
            rule_key=rule_key,
            task_id=task_id,
        )
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            self._pending[aid]["scope"] = result
            return True, result
        except asyncio.TimeoutError:
            self._pending[aid]["scope"] = "timeout"
            return False, "timeout"
        finally:
            self._futures.pop(aid, None)

    def respond(self, approval_id: str, approved: bool, scope: str = "once") -> bool:
        future = self._futures.get(approval_id)
        if future is None or future.done():
            return False
        future.set_result(scope if approved else "deny")
        return True

    def pending(self) -> list[dict[str, Any]]:
        return list(self._pending.values())
