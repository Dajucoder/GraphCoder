"""SQLite is the single authority for GraphCoder runtime state.

Runtime events are append-only: model messages, tool calls, tool results,
permission decisions and termination facts are all rows. Sessions, task
projections, UI views and recovery are projections over that log.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite

from src.utils.settings import graphcoder_home

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    archived    INTEGER NOT NULL DEFAULT 0,
    parent_id   TEXT,
    branch_point TEXT
);

CREATE TABLE IF NOT EXISTS runtime_events (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    turn_id     TEXT NOT NULL,
    item_id     TEXT,
    type        TEXT NOT NULL,
    payload     TEXT NOT NULL,
    ts          REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session ON runtime_events(session_id, seq);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    mode        TEXT NOT NULL,
    status      TEXT NOT NULL,
    content     TEXT NOT NULL,
    budgets     TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS permissions (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    kind    TEXT NOT NULL,
    pattern TEXT NOT NULL,
    action  TEXT NOT NULL,
    source  TEXT NOT NULL,
    ts      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT,
    task_id       TEXT,
    provider      TEXT,
    model         TEXT,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost          REAL NOT NULL DEFAULT 0,
    ts            REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id   TEXT,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    ts          REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL,
    path        TEXT NOT NULL,
    size        INTEGER NOT NULL DEFAULT 0,
    ts          REAL NOT NULL
);
"""


def _now() -> float:
    return time.time()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


class SqliteStore:
    """Async SQLite store implementing the Codex/Maka-style runtime authority."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (graphcoder_home() / "runtime.sqlite")
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self.path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _db_or_raise(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SQLite store not connected")
        return self._db

    # ---------------- sessions ----------------
    async def create_session(
        self,
        title: str = "新会话",
        parent_id: str | None = None,
        branch_point: str | None = None,
    ) -> dict[str, Any]:
        sid = new_id("s_")
        now = _now()
        await self._db_or_raise().execute(
            "INSERT INTO sessions (id, title, created_at, updated_at, archived, parent_id, branch_point) VALUES (?,?,?,?,0,?,?)",
            (sid, title, now, now, parent_id, branch_point),
        )
        await self._db_or_raise().commit()
        return {
            "id": sid,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "archived": 0,
            "parent_id": parent_id,
            "branch_point": branch_point,
        }

    async def list_sessions(self, include_archived: bool = False) -> list[dict[str, Any]]:
        where = "" if include_archived else "WHERE archived = 0"
        cursor = await self._db_or_raise().execute(
            f"SELECT id, title, created_at, updated_at, archived, parent_id, branch_point "
            f"FROM sessions {where} ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_session(self, sid: str) -> dict[str, Any] | None:
        cursor = await self._db_or_raise().execute(
            "SELECT * FROM sessions WHERE id = ?", (sid,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def rename_session(self, sid: str, title: str) -> bool:
        cur = await self._db_or_raise().execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, _now(), sid),
        )
        await self._db_or_raise().commit()
        return cur.rowcount > 0

    async def archive_session(self, sid: str, archived: bool = True) -> bool:
        cur = await self._db_or_raise().execute(
            "UPDATE sessions SET archived = ?, updated_at = ? WHERE id = ?",
            (1 if archived else 0, _now(), sid),
        )
        await self._db_or_raise().commit()
        return cur.rowcount > 0

    async def fork_session(self, parent_id: str, branch_point: str | None = None) -> dict[str, Any] | None:
        parent = await self.get_session(parent_id)
        if parent is None:
            return None
        branch = await self.create_session(
            title=f"{parent['title']} (分支)", parent_id=parent_id, branch_point=branch_point
        )
        # Copy events up to branch_point (or all).
        events = await self.events(parent_id)
        for ev in events:
            if branch_point and ev["seq"] > int(branch_point or 0):
                break
            await self.append_event(
                branch["id"],
                turn_id=ev["turn_id"],
                item_id=ev["item_id"],
                type=ev["type"],
                payload=ev["payload"],
                ts=ev["ts"],
            )
        return branch

    async def delete_session(self, sid: str) -> bool:
        cur = await self._db_or_raise().execute("DELETE FROM sessions WHERE id = ?", (sid,))
        await self._db_or_raise().execute("DELETE FROM runtime_events WHERE session_id = ?", (sid,))
        await self._db_or_raise().execute("DELETE FROM tasks WHERE session_id = ?", (sid,))
        await self._db_or_raise().commit()
        return cur.rowcount > 0

    # ---------------- runtime events ----------------
    async def append_event(
        self,
        session_id: str,
        turn_id: str,
        type: str,
        payload: dict[str, Any],
        item_id: str | None = None,
        ts: float | None = None,
    ) -> dict[str, Any]:
        event = {
            "session_id": session_id,
            "turn_id": turn_id,
            "item_id": item_id,
            "type": type,
            "payload": payload,
            "ts": ts or _now(),
        }
        await self._db_or_raise().execute(
            "INSERT INTO runtime_events (session_id, turn_id, item_id, type, payload, ts) VALUES (?,?,?,?,?,?)",
            (
                session_id,
                turn_id,
                item_id,
                type,
                json.dumps(payload, ensure_ascii=False),
                event["ts"],
            ),
        )
        await self._db_or_raise().execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (event["ts"], session_id)
        )
        await self._db_or_raise().commit()
        return event

    async def events(self, session_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        cursor = await self._db_or_raise().execute(
            "SELECT seq, session_id, turn_id, item_id, type, payload, ts "
            "FROM runtime_events WHERE session_id = ? AND seq > ? ORDER BY seq",
            (session_id, after_seq),
        )
        rows = await cursor.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload"])
            out.append(d)
        return out

    # ---------------- tasks ----------------
    async def create_task(
        self, session_id: str, mode: str, content: str, budgets: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        tid = new_id("t_")
        now = _now()
        await self._db_or_raise().execute(
            "INSERT INTO tasks (id, session_id, mode, status, content, budgets, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (tid, session_id, mode, "pending", content, json.dumps(budgets or {}), now, now),
        )
        await self._db_or_raise().commit()
        return {
            "id": tid,
            "session_id": session_id,
            "mode": mode,
            "status": "pending",
            "content": content,
            "budgets": budgets or {},
            "created_at": now,
            "updated_at": now,
        }

    async def update_task(self, tid: str, **fields: Any) -> None:
        if not fields:
            return
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = [json.dumps(v) if k == "budgets" else v for k, v in fields.items()]
        await self._db_or_raise().execute(
            f"UPDATE tasks SET {sets}, updated_at = ? WHERE id = ?",
            (*values, _now(), tid),
        )
        await self._db_or_raise().commit()

    async def get_task(self, tid: str) -> dict[str, Any] | None:
        cursor = await self._db_or_raise().execute("SELECT * FROM tasks WHERE id = ?", (tid,))
        row = await cursor.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["budgets"] = json.loads(d.get("budgets") or "{}")
        return d

    async def list_tasks(self, session_id: str | None = None) -> list[dict[str, Any]]:
        if session_id:
            cursor = await self._db_or_raise().execute(
                "SELECT * FROM tasks WHERE session_id = ? ORDER BY created_at DESC", (session_id,)
            )
        else:
            cursor = await self._db_or_raise().execute("SELECT * FROM tasks ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["budgets"] = json.loads(d.get("budgets") or "{}")
            out.append(d)
        return out

    # ---------------- settings ----------------
    async def get_setting(self, key: str, default: Any = None) -> Any:
        cursor = await self._db_or_raise().execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        if row is None:
            return default
        return json.loads(row["value"])

    async def set_setting(self, key: str, value: Any) -> None:
        await self._db_or_raise().execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        await self._db_or_raise().commit()

    # ---------------- permissions ----------------
    async def list_permissions(self) -> list[dict[str, Any]]:
        cursor = await self._db_or_raise().execute(
            "SELECT * FROM permissions ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def add_permission(
        self, kind: str, pattern: str, action: str, source: str = "policy"
    ) -> None:
        await self._db_or_raise().execute(
            "INSERT INTO permissions (kind, pattern, action, source, ts) VALUES (?,?,?,?,?)",
            (kind, pattern, action, source, _now()),
        )
        await self._db_or_raise().commit()

    async def delete_permission(self, pid: int) -> bool:
        cur = await self._db_or_raise().execute("DELETE FROM permissions WHERE id = ?", (pid,))
        await self._db_or_raise().commit()
        return cur.rowcount > 0

    # ---------------- usage ----------------
    async def add_usage(self, usage: dict[str, Any]) -> None:
        await self._db_or_raise().execute(
            "INSERT INTO usage (session_id, task_id, provider, model, input_tokens, output_tokens, cost, ts) VALUES (?,?,?,?,?,?,?,?)",
            (
                usage.get("session_id"),
                usage.get("task_id"),
                usage.get("provider"),
                usage.get("model"),
                usage.get("input_tokens", 0),
                usage.get("output_tokens", 0),
                usage.get("cost", 0),
                _now(),
            ),
        )
        await self._db_or_raise().commit()

    # ---------------- memory ----------------
    async def add_memory(self, thread_id: str | None, key: str, value: str) -> dict[str, Any]:
        cursor = await self._db_or_raise().execute(
            "INSERT INTO memory (thread_id, key, value, ts) VALUES (?,?,?,?)",
            (thread_id, key, value, _now()),
        )
        await self._db_or_raise().commit()
        return {"id": cursor.lastrowid, "thread_id": thread_id, "key": key, "value": value}

    async def list_memory(self, thread_id: str | None = None, query: str = "") -> list[dict[str, Any]]:
        if thread_id:
            cursor = await self._db_or_raise().execute(
                "SELECT * FROM memory WHERE thread_id = ? ORDER BY id DESC", (thread_id,)
            )
        else:
            cursor = await self._db_or_raise().execute("SELECT * FROM memory ORDER BY id DESC")
        rows = await cursor.fetchall()
        out = [dict(r) for r in rows]
        if query:
            q = query.lower()
            out = [m for m in out if q in m["key"].lower() or q in str(m["value"]).lower()]
        return out

    async def delete_memory(self, memory_id: int) -> bool:
        cur = await self._db_or_raise().execute("DELETE FROM memory WHERE id = ?", (memory_id,))
        await self._db_or_raise().commit()
        return cur.rowcount > 0

    # ---------------- artifacts ----------------
    async def record_artifact(self, task_id: str, path: str, size: int) -> None:
        await self._db_or_raise().execute(
            "INSERT INTO artifacts (task_id, path, size, ts) VALUES (?,?,?,?)",
            (task_id, path, size, _now()),
        )
        await self._db_or_raise().commit()

    async def list_artifacts(self, task_id: str) -> list[dict[str, Any]]:
        cursor = await self._db_or_raise().execute(
            "SELECT id, task_id, path, size, ts FROM artifacts WHERE task_id = ? ORDER BY id",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
