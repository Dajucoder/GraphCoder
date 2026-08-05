"""Persistent store tests."""

from __future__ import annotations

from src.data.store import Store


def test_session_crud(tmp_path) -> None:
    store = Store(tmp_path)
    session = store.create_session("测试会话")
    assert store.get_session(session["id"]) is not None
    store.append_message(session["id"], {"role": "user", "content": "hi"})
    stored = store.get_session(session["id"])
    assert stored is not None
    assert stored["messages"][0]["content"] == "hi"
    assert store.list_sessions()[0]["message_count"] == 1
    assert store.delete_session(session["id"]) is True
    assert store.get_session(session["id"]) is None


def test_task_events(tmp_path) -> None:
    store = Store(tmp_path)
    session = store.create_session()
    task = store.create_task(session["id"], "chat", "hello")
    store.append_task_event(task["id"], {"type": "text", "delta": "x"})
    task_data = store.get_task(task["id"])
    assert task_data is not None
    assert task_data["status"] == "pending"
    assert len(task_data["events"]) == 1
    store.update_task(task["id"], status="completed")
    completed = store.get_task(task["id"])
    assert completed is not None
    assert completed["status"] == "completed"
