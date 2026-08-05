"""Async JSON-RPC lite client for the GraphCoder app-server (stdio)."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

NotificationHandler = Callable[[str, dict[str, Any]], Awaitable[None] | None]


def runtime_python() -> str:
    """Locate the Python interpreter that can run the app-server."""
    env = os.getenv("GRAPHCODER_RUNTIME_PYTHON")
    if env:
        return env
    # Prefer the interpreter that launched us (the conda env python has all deps).
    return sys.executable


class RpcClient:
    """Spawns the app-server child process and speaks JSON-RPC over stdio."""

    def __init__(
        self,
        *,
        workspace: Path,
        home: Path | None = None,
        on_notification: NotificationHandler | None = None,
        python: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.workspace = workspace
        self.home = home
        self.python = python or runtime_python()
        self.on_notification = on_notification
        self.timeout = timeout
        self._proc: asyncio.subprocess.Process | None = None
        self._pending: dict[Any, asyncio.Future] = {}
        self._seq = 0
        self._reader_task: asyncio.Task | None = None

    async def start(self) -> None:
        repo = Path(__file__).resolve().parent.parent.parent
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo)
        if self.home is not None:
            env["GRAPHCODER_HOME"] = str(self.home)
        self._proc = await asyncio.create_subprocess_exec(
            self.python,
            "-m",
            "src.api.app_server",
            "--workspace",
            str(self.workspace),
            *(["--home", str(self.home)] if self.home else []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=(
                None
                if os.getenv("GRAPHCODER_RUNTIME_DEBUG")
                else asyncio.subprocess.DEVNULL
            ),
            env=env,
        )
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            if "id" in msg:
                future = self._pending.pop(msg["id"], None)
                if future and not future.done():
                    if "error" in msg:
                        future.set_exception(RuntimeError(msg["error"].get("message", "RPC error")))
                    else:
                        future.set_result(msg.get("result"))
            elif "method" in msg and self.on_notification:
                handler = self.on_notification(msg["method"], msg.get("params", {}))
                if asyncio.iscoroutine(handler):
                    # Fire-and-forget: the read loop must keep draining responses
                    # (e.g. approvals/respond) while the handler awaits requests.
                    asyncio.create_task(handler)

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        assert self._proc and self._proc.stdin
        self._seq += 1
        req_id = self._seq
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[req_id] = future
        payload = json.dumps({"id": req_id, "method": method, "params": params or {}}, ensure_ascii=False)
        self._proc.stdin.write((payload + "\n").encode("utf-8"))
        await self._proc.stdin.drain()
        try:
            return await asyncio.wait_for(future, timeout=self.timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"RPC 超时: {method}")

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.close()
            except Exception as exc:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).debug("关闭 stdin 失败: %s", exc)
        if self._proc:
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except (asyncio.TimeoutError, ProcessLookupError):
                self._proc.kill()
