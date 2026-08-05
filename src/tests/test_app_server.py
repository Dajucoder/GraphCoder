"""App-server protocol tests (in-process dispatch)."""

from __future__ import annotations

import asyncio
import io

from src.api.app_server import AppServer
from src.storage.sqlite_store import SqliteStore
from src.utils.settings import SettingsStore


def _make_server(tmp_path):
    async def run() -> tuple[AppServer, io.StringIO]:
        store = SqliteStore(tmp_path / "runtime.sqlite")
        settings = SettingsStore(tmp_path / "settings.json")
        out = io.StringIO()
        server = AppServer(store=store, settings=settings, workspace=tmp_path, stdin=io.StringIO(""), stdout=out)
        await server.start()
        return server, out

    return asyncio.run(run())


def test_initialize_handshake(tmp_path) -> None:
    server, _ = _make_server(tmp_path)

    async def run() -> None:
        result = await server.rpc_initialize({})
        assert result["protocolVersion"] == "1.0"
        assert "threads" in result["capabilities"]
        await server.store.close()

    asyncio.run(run())


def test_thread_lifecycle_rpc(tmp_path) -> None:
    server, _ = _make_server(tmp_path)

    async def run() -> None:
        thread = await server.rpc_threads_create({"title": "协议"})
        assert thread["id"]
        listed = await server.rpc_threads_list({})
        assert listed["threads"][0]["id"] == thread["id"]
        detail = await server.rpc_threads_get({"thread_id": thread["id"]})
        assert "events" in detail
        await server.store.close()

    asyncio.run(run())


def test_dispatch_unknown_method(tmp_path) -> None:
    server, out = _make_server(tmp_path)

    async def run() -> None:
        await server.dispatch({"id": 1, "method": "does_not_exist"})
        assert "error" in out.getvalue()
        await server.store.close()

    asyncio.run(run())
