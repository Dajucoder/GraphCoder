"""One-time migration from the v1 JSON store into the SQLite authority."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from src.storage.sqlite_store import SqliteStore
from src.utils.logging import get_logger

log = get_logger(__name__)


async def migrate_v1_json(store: SqliteStore, v1_root: Path) -> int:
    """Import legacy JSON sessions/tasks/events. Returns imported session count."""
    if await store.get_setting("migrated_v1_json", False):
        return 0
    sessions_dir = v1_root / "sessions"
    tasks_dir = v1_root / "tasks"
    if not sessions_dir.exists():
        await store.set_setting("migrated_v1_json", True)
        return 0

    imported = 0
    for path in sorted(sessions_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("跳过损坏的会话文件 %s: %s", path, exc)
            continue
        sid = data.get("id") or path.stem
        session = await store.create_session(
            title=data.get("title", "迁移会话"),
        )
        turn_id = ""
        for msg in data.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            turn_id = turn_id or "migrated"
            await store.append_event(
                session["id"],
                turn_id=turn_id,
                type=f"message/{role}",
                payload={"content": content, "ts": msg.get("ts")},
            )
        # Import tasks referencing this session (by old id) as events snapshot.
        for task_path in sorted(tasks_dir.glob("*.json")):
            try:
                task = json.loads(task_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if task.get("session_id") != sid:
                continue
            task_id = await _import_task(store, session["id"], task)
            for event in task.get("events", []):
                await store.append_event(
                    session["id"],
                    turn_id=task_id,
                    item_id=event.get("id"),
                    type=event.get("type", "unknown"),
                    payload=event,
                    ts=event.get("ts"),
                )
        imported += 1

    await store.set_setting("migrated_v1_json", True)
    log.info("v1 JSON 迁移完成：%d 个会话", imported)
    return imported


async def _import_task(store: SqliteStore, session_id: str, task: dict[str, Any]) -> str:
    from src.storage.sqlite_store import new_id

    tid = new_id("t_")
    # Keep the same public id when possible (SQLite primary key collision unlikely).
    await store._db_or_raise().execute(
        "INSERT INTO tasks (id, session_id, mode, status, content, budgets, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            tid,
            session_id,
            task.get("mode", "chat"),
            task.get("status", "unknown"),
            task.get("content", ""),
            "{}",
            task.get("created_at", 0),
            task.get("updated_at", 0),
        ),
    )
    await store._db_or_raise().commit()
    return tid


def backup_v1_data(v1_root: Path, backup_dir: Path) -> None:
    """Copy the legacy JSON store to a backup directory before migration."""
    if not v1_root.exists():
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(v1_root, backup_dir / "v1-json", dirs_exist_ok=True)
