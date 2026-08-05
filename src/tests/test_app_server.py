"""App-server protocol tests (in-process dispatch)."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

import pytest

from src.api.app_server import AppServer
from src.providers.openai_compat import OpenAICompatProvider
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
        assert result["capabilities"]["workspace"] == ["get", "set", "files"]
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


def test_workspace_lifecycle_and_file_listing(tmp_path) -> None:
    server, out = _make_server(tmp_path)
    workspace = tmp_path / "project"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (workspace / "README.md").write_text("# Project\n", encoding="utf-8")
    (workspace / "node_modules").mkdir()

    async def run() -> None:
        result = await server.rpc_workspace_set({"path": str(workspace)})
        assert result["path"] == str(workspace)
        assert result["name"] == "project"
        assert server.threads.workspace == workspace
        assert server.threads.adapter.workspace == workspace
        assert server.settings.options()["workspace"] == str(workspace)
        assert "workspace/changed" in out.getvalue()

        root = await server.rpc_workspace_files({"path": "."})
        assert [(entry["name"], entry["kind"]) for entry in root["entries"]] == [
            ("src", "directory"),
            ("README.md", "file"),
        ]
        nested = await server.rpc_workspace_files({"path": "src"})
        assert nested["entries"][0]["path"] == "src/main.py"
        with pytest.raises(KeyError):
            await server.rpc_workspace_files({"path": "../"})
        await server.store.close()

    asyncio.run(run())


def test_workspace_switch_is_blocked_while_task_is_running(tmp_path) -> None:
    server, _ = _make_server(tmp_path)
    target = tmp_path / "other"
    target.mkdir()

    async def run() -> None:
        blocker = asyncio.create_task(asyncio.sleep(10))
        server.threads._running["task"] = blocker
        try:
            with pytest.raises(KeyError, match="任务运行期间"):
                await server.rpc_workspace_set({"path": str(target)})
        finally:
            blocker.cancel()
        await server.store.close()

    asyncio.run(run())


def test_memory_add_validates_and_persists(tmp_path) -> None:
    server, _ = _make_server(tmp_path)

    async def run() -> None:
        memory = await server.rpc_memory_add({"key": "style", "value": "Use pytest"})
        assert memory["key"] == "style"
        listed = await server.rpc_memory_list({})
        assert listed["memory"][0]["value"] == "Use pytest"
        with pytest.raises(KeyError):
            await server.rpc_memory_add({"key": "", "value": "missing key"})
        await server.store.close()

    asyncio.run(run())


def test_settings_set_rebuilds_provider_without_mutating_request(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    server, _ = _make_server(tmp_path)
    params = {"options": {"active_provider": "deepseek", "max_iterations": 12}}

    async def run() -> None:
        result = await server.rpc_settings_set(params)
        assert result == {"ok": True}
        assert params["options"]["active_provider"] == "deepseek"
        assert server.settings.active_provider_id() == "deepseek"
        assert server.threads.adapter.cfg.id == "deepseek"
        assert isinstance(server.threads.adapter.provider, OpenAICompatProvider)
        assert server.options["max_iterations"] == 12
        assert server.threads.options["max_iterations"] == 12
        assert server.threads.adapter.options["max_iterations"] == 12
        await server.store.close()

    asyncio.run(run())


def test_custom_provider_lifecycle_never_returns_secret(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    server, _ = _make_server(tmp_path)

    async def run() -> None:
        provider = await server.rpc_providers_upsert(
            {
                "name": "My endpoint",
                "kind": "openai-compatible",
                "base_url": "https://example.test/v1",
                "api_key": "secret-value",
                "model": "test-model",
            }
        )
        assert provider["id"].startswith("custom-")
        assert provider["has_key"] is True
        assert provider["custom"] is True
        assert "api_key" not in provider

        second = await server.rpc_providers_upsert(
            {
                "name": "Second endpoint",
                "kind": "openai-compatible",
                "base_url": "https://second.example.test/v1",
                "api_key": "second-secret",
                "model": "second-model",
            }
        )
        assert second["id"] != provider["id"]

        models = await server.rpc_models_list({})
        custom = next(item for item in models["models"] if item["id"] == provider["id"])
        assert "api_key" not in custom

        await server.rpc_settings_set({"options": {"active_provider": provider["id"]}})
        assert server.threads.adapter.cfg.model == "test-model"
        result = await server.rpc_providers_delete({"id": provider["id"]})
        assert result == {"ok": True}
        assert server.settings.active_provider_id() is None
        assert server.threads.adapter.cfg.id == "openai"

        replacement = await server.rpc_providers_upsert(
            {
                "name": "Replacement endpoint",
                "kind": "openai-compatible",
                "base_url": "https://replacement.example.test/v1",
                "api_key": "replacement-secret",
                "model": "replacement-model",
            }
        )
        assert replacement["id"] != second["id"]
        saved_ids = {item.id for item in server.settings.custom_providers()}
        assert saved_ids == {second["id"], replacement["id"]}
        await server.store.close()

    asyncio.run(run())


def test_saved_workspace_path_is_stored_as_absolute(tmp_path) -> None:
    server, _ = _make_server(tmp_path)

    async def run() -> None:
        info = await server.rpc_workspace_get({})
        assert Path(info["path"]).is_absolute()
        await server.store.close()

    asyncio.run(run())
