"""SQLite store tests."""

from __future__ import annotations

import asyncio

from src.storage.migrate import migrate_v1_json
from src.storage.sqlite_store import SqliteStore


def _run(coro):
    return asyncio.run(coro)


def test_store_crud(tmp_path) -> None:
    async def run() -> None:
        store = SqliteStore(tmp_path / "runtime.sqlite")
        await store.connect()
        session = await store.create_session("测试")
        assert (await store.get_session(session["id"])) is not None
        await store.append_event(
            session["id"], turn_id="t1", type="item/started", payload={"kind": "agent_message"}
        )
        events = await store.events(session["id"])
        assert len(events) == 1
        assert events[0]["payload"]["kind"] == "agent_message"
        task = await store.create_task(session["id"], "chat", "hi")
        await store.update_task(task["id"], status="completed")
        stored_task = await store.get_task(task["id"])
        assert stored_task is not None
        assert stored_task["status"] == "completed"
        await store.add_permission("command", "git *", "allow")
        assert len(await store.list_permissions()) == 1
        await store.close()

    _run(run())


def test_fork_copies_events(tmp_path) -> None:
    async def run() -> None:
        store = SqliteStore(tmp_path / "runtime.sqlite")
        await store.connect()
        parent = await store.create_session("父")
        await store.append_event(parent["id"], turn_id="t", type="item/completed", payload={"content": "a"})
        branch = await store.fork_session(parent["id"])
        assert branch is not None
        assert len(await store.events(branch["id"])) == 1
        await store.close()

    _run(run())


def test_migrate_v1_json(tmp_path) -> None:
    async def run() -> None:
        v1 = tmp_path / "v1"
        (v1 / "sessions").mkdir(parents=True)
        (v1 / "tasks").mkdir()
        import json

        (v1 / "sessions" / "s1.json").write_text(
            json.dumps({"id": "s1", "title": "旧会话", "messages": [{"role": "user", "content": "你好"}]}),
            encoding="utf-8",
        )
        (v1 / "tasks" / "t1.json").write_text(
            json.dumps({"id": "t1", "session_id": "s1", "mode": "chat", "content": "hi", "events": [{"type": "text", "delta": "x"}]}),
            encoding="utf-8",
        )
        store = SqliteStore(tmp_path / "runtime.sqlite")
        await store.connect()
        count = await migrate_v1_json(store, v1)
        assert count == 1
        sessions = await store.list_sessions()
        assert len(sessions) == 1
        assert len(await store.events(sessions[0]["id"])) >= 2  # message + task events
        assert await store.get_setting("migrated_v1_json") is True
        # idempotent
        assert await migrate_v1_json(store, v1) == 0
        await store.close()

    _run(run())
