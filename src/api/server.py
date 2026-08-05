"""Web transport: thin FastAPI layer bridging HTTP/SSE to the app-server child.

All functionality lives in the GraphCoder Runtime (app-server child process);
this module only proxies JSON-RPC and streams notifications.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.cli.rpc_client import RpcClient
from src.utils.logging import get_logger

log = get_logger(__name__)


class RuntimeBridge:
    """Owns one app-server child process and fans out notifications."""

    def __init__(self, workspace: Path, home: Path | None = None) -> None:
        self.workspace = workspace
        self.home = home
        self.client: RpcClient | None = None
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self.client = RpcClient(workspace=self.workspace, home=self.home, on_notification=self._notify)
        await self.client.start()
        await self.client.request("initialize", {})
        log.info("运行时桥已连接 (workspace=%s)", self.workspace)

    async def close(self) -> None:
        if self.client:
            await self.client.close()

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait({"method": method, "params": params})
            except asyncio.QueueFull:
                pass

    async def request(self, method: str, params: dict[str, Any]) -> Any:
        if self.client is None:
            raise RuntimeError("运行时未就绪")
        return await self.client.request(method, params)

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(queue)


def create_app(
    *,
    workspace: Path | None = None,
    home: Path | None = None,
    bridge: RuntimeBridge | None = None,
) -> FastAPI:
    workspace = (workspace or Path.cwd()).resolve()
    bridge = bridge or RuntimeBridge(workspace, home)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await bridge.start()
        yield
        await bridge.close()

    app = FastAPI(title="GraphCoder Web Transport", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "workspace": str(workspace), "version": "2.0.0"}

    @app.post("/api/v1/rpc")
    async def rpc(request: Request) -> JSONResponse:
        body = await request.json()
        method = body.get("method", "")
        params = body.get("params") or {}
        try:
            result = await bridge.request(method, params)
            return JSONResponse({"result": result})
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(
                {"error": {"code": -32000, "message": f"{type(exc).__name__}: {exc}"}},
                status_code=400,
            )

    @app.get("/api/v1/stream")
    async def stream() -> StreamingResponse:
        queue = await bridge.subscribe()

        async def generator():
            try:
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15)
                        yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keep-alive\n\n"
            finally:
                await bridge.unsubscribe(queue)

        return StreamingResponse(generator(), media_type="text/event-stream")

    # ---- thin adapters: keep v1 REST contract working during transition ----
    @app.get("/api/v1/sessions")
    async def list_sessions() -> dict[str, Any]:
        return await bridge.request("threads/list", {})

    @app.post("/api/v1/sessions")
    async def create_session(request: Request) -> dict[str, Any]:
        body = await request.json()
        return await bridge.request("threads/create", {"title": body.get("title", "新会话")})

    @app.get("/api/v1/sessions/{sid}")
    async def get_session(sid: str) -> dict[str, Any]:
        return await bridge.request("threads/get", {"thread_id": sid})

    @app.delete("/api/v1/sessions/{sid}")
    async def delete_session(sid: str) -> dict[str, Any]:
        return await bridge.request("threads/delete", {"thread_id": sid})

    @app.post("/api/v1/sessions/{sid}/messages")
    async def send_message(sid: str, request: Request) -> dict[str, Any]:
        body = await request.json()
        return await bridge.request(
            "threads/prompt",
            {
                "thread_id": sid,
                "content": body.get("content", ""),
                "mode": body.get("mode", "chat"),
            },
        )

    @app.get("/api/v1/providers")
    async def providers() -> dict[str, Any]:
        return await bridge.request("models/list", {})

    @app.post("/api/v1/approvals/{aid}")
    async def respond_approval(aid: str, request: Request) -> dict[str, Any]:
        body = await request.json()
        return await bridge.request(
            "approvals/respond",
            {"id": aid, "approved": body.get("approved", False)},
        )

    @app.get("/api/v1/settings")
    async def get_settings() -> dict[str, Any]:
        return await bridge.request("settings/get", {})

    # ---- static web ----
    dist = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")

    return app


app = create_app()
