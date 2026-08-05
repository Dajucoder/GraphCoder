"""Persistent store for sessions, tasks and events."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger
from src.utils.settings import graphcoder_home

log = get_logger(__name__)


def _now() -> float:
    return time.time()


class Store:
    """JSON-file backed store under the GraphCoder home directory."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or graphcoder_home()
        self.sessions_dir = self.root / "sessions"
        self.tasks_dir = self.root / "tasks"
        self.artifacts_dir = self.root / "artifacts"
        for d in (self.sessions_dir, self.tasks_dir, self.artifacts_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ---------------- sessions ----------------
    def create_session(self, title: str = "新会话") -> dict[str, Any]:
        sid = uuid.uuid4().hex[:12]
        session = {
            "id": sid,
            "title": title,
            "created_at": _now(),
            "updated_at": _now(),
            "messages": [],
        }
        self._write_json(self.sessions_dir / f"{sid}.json", session)
        return session

    def list_sessions(self) -> list[dict[str, Any]]:
        sessions = []
        for path in sorted(self.sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            data = self._read_json(path)
            if data:
                sessions.append(
                    {
                        "id": data["id"],
                        "title": data["title"],
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "message_count": len(data.get("messages", [])),
                    }
                )
        return sessions

    def get_session(self, sid: str) -> dict[str, Any] | None:
        return self._read_json(self.sessions_dir / f"{sid}.json")

    def append_message(self, sid: str, message: dict[str, Any]) -> None:
        session = self.get_session(sid)
        if session is None:
            raise KeyError(f"会话不存在: {sid}")
        session.setdefault("messages", []).append(message)
        session["updated_at"] = _now()
        self._write_json(self.sessions_dir / f"{sid}.json", session)

    def rename_session(self, sid: str, title: str) -> bool:
        session = self.get_session(sid)
        if session is None:
            return False
        session["title"] = title
        self._write_json(self.sessions_dir / f"{sid}.json", session)
        return True

    def delete_session(self, sid: str) -> bool:
        path = self.sessions_dir / f"{sid}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    # ---------------- tasks ----------------
    def create_task(self, session_id: str, mode: str, content: str) -> dict[str, Any]:
        tid = uuid.uuid4().hex[:12]
        task = {
            "id": tid,
            "session_id": session_id,
            "mode": mode,
            "content": content,
            "status": "pending",
            "created_at": _now(),
            "updated_at": _now(),
            "events": [],
            "result": "",
        }
        self._write_json(self.tasks_dir / f"{tid}.json", task)
        return task

    def update_task(self, tid: str, **fields: Any) -> None:
        task = self.get_task(tid)
        if task is None:
            return
        task.update(fields)
        task["updated_at"] = _now()
        self._write_json(self.tasks_dir / f"{tid}.json", task)

    def get_task(self, tid: str) -> dict[str, Any] | None:
        return self._read_json(self.tasks_dir / f"{tid}.json")

    def append_task_event(self, tid: str, event: dict[str, Any]) -> None:
        task = self.get_task(tid)
        if task is None:
            return
        task["events"].append(event)
        self._write_json(self.tasks_dir / f"{tid}.json", task)

    def list_tasks(self, session_id: str) -> list[dict[str, Any]]:
        tasks = []
        for path in sorted(self.tasks_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            data = self._read_json(path)
            if data and data.get("session_id") == session_id:
                tasks.append(
                    {
                        "id": data["id"],
                        "mode": data.get("mode"),
                        "content": data.get("content"),
                        "status": data.get("status"),
                        "created_at": data.get("created_at"),
                        "event_count": len(data.get("events", [])),
                    }
                )
        return tasks

    # ---------------- artifacts ----------------
    def artifact_tree(self, task_id: str) -> dict[str, Any]:
        base = self.artifacts_dir / task_id
        if not base.exists():
            return {"task_id": task_id, "files": []}
        files = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                files.append(
                    {
                        "path": str(path.relative_to(base)),
                        "size": path.stat().st_size,
                    }
                )
        return {"task_id": task_id, "files": files}

    def artifact_path(self, task_id: str, rel_path: str) -> Path | None:
        base = (self.artifacts_dir / task_id).resolve()
        target = (base / rel_path).resolve()
        if target.is_relative_to(base) and target.exists() and target.is_file():
            return target
        return None

    # ---------------- helpers ----------------
    def _read_json(self, path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            log.warning("读取 %s 失败: %s", path, exc)
            return None

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
