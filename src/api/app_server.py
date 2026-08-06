"""GraphCoder app-server: JSON-RPC lite over stdio (JSONL).

Models Codex App Server semantics: Item / Turn / Thread primitives, an
``initialize`` handshake, bidirectional requests (approvals pause a turn until
the client responds) and notifications for progress.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from src.providers.base import ProviderConfig
from src.providers.registry import BUILTIN_PRESETS, resolve_provider
from src.runtime.approvals import ApprovalHub
from src.runtime.engine import AgentEngine
from src.runtime.events import EventBus
from src.runtime.permission import PermissionEngine
from src.runtime.threads import ThreadManager
from src.storage.migrate import migrate_v1_json
from src.storage.sqlite_store import SqliteStore
from src.utils.logging import get_logger
from src.utils.settings import SettingsStore, graphcoder_home

log = get_logger(__name__)

PROTOCOL_VERSION = "1.0"
APP_VERSION = "2.1.0"


class AppServer:
    """Hosts runtime threads and speaks JSON-RPC lite over stdio."""

    def __init__(
        self,
        *,
        store: SqliteStore,
        settings: SettingsStore,
        workspace: Path,
        stdin=None,
        stdout=None,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self.workspace = workspace
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.options = options or {}
        self._started_at = time.time()
        self.bus = EventBus()
        self.approvals = ApprovalHub(bus=self.bus)

        adapter = AgentEngine(
            provider_config=self._resolve_provider(),
            bus=self.bus,
            approvals=self.approvals,
            options=self.options,
            workspace=self.workspace,
            store=self.store,
        )
        self.threads = ThreadManager(
            store=self.store,
            adapter=adapter,
            bus=self.bus,
            workspace=self.workspace,
            options=self.options,
        )

    # ------------------------------------------------------------------
    async def start(self) -> None:
        await self.store.connect()
        v1_home = os.getenv("GRAPHCODER_V1_HOME")
        v1_root = Path(v1_home) if v1_home else graphcoder_home()
        await migrate_v1_json(self.store, v1_root)

        # load permission rules from SQLite
        rules = await self.store.list_permissions()
        engine = PermissionEngine()
        engine.load_rules([dict(r) for r in rules])
        # Rebuild the engine's permission engine so policy applies at turn time.
        self.threads.adapter.permission = engine

        # bus listener: notify client + persist runtime events
        def on_event(event_type: str, payload: dict[str, Any]) -> None:
            self._notify(event_type, payload)
            thread_id = payload.get("thread_id") or payload.get("session_id")
            if thread_id:
                asyncio.create_task(
                    self.store.append_event(
                        session_id=thread_id,
                        turn_id=payload.get("turn_id") or "",
                        type=event_type,
                        payload=payload,
                        item_id=payload.get("item_id"),
                        ts=payload.get("ts"),
                    )
                )

        self.bus.set_listener(on_event)
        active_cfg = self._resolve_provider()
        log.info(
            "启动 Provider: %s (%s) kind=%s base_url=%s model=%s has_key=%s",
            active_cfg.name,
            active_cfg.id,
            active_cfg.kind,
            active_cfg.base_url or "默认",
            active_cfg.model,
            bool(active_cfg.resolved_api_key()),
        )


    def _resolve_provider(self) -> ProviderConfig:
        return resolve_provider(
            custom_providers=self.settings.custom_providers(),
            active_id=self.settings.active_provider_id(),
        )

    # ------------------------------------------------------------------
    def _notify(self, method: str, params: dict[str, Any]) -> None:
        line = json.dumps({"method": method, "params": params}, ensure_ascii=False)
        self.stdout.write(line + "\n")
        self.stdout.flush()

    def _respond(self, req_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> None:
        msg: dict[str, Any] = {"id": req_id}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result
        self.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.stdout.flush()

    # ------------------------------------------------------------------
    async def dispatch(self, req: dict[str, Any]) -> None:
        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params") or {}
        handler = getattr(self, f"rpc_{method.replace('/', '_')}", None)
        if handler is None:
            self._respond(req_id, error={"code": -32601, "message": f"未知方法: {method}"})
            return
        try:
            result = await handler(params)
            self._respond(req_id, result=result)
        except KeyError as exc:
            self._respond(req_id, error={"code": -32602, "message": str(exc)})
        except Exception as exc:  # noqa: BLE001 - RPC 必须兜底响应错误
            log.error("RPC %s 失败: %s", method, exc)
            self._respond(req_id, error={"code": -32000, "message": f"{type(exc).__name__}: {exc}"})

    async def run_forever(self) -> None:
        await self.start()
        self._notify("server/ready", {"workspace": str(self.workspace), "protocol": PROTOCOL_VERSION})
        log.info("app-server 就绪 (workspace=%s)", self.workspace)
        # Read stdin from a worker thread so the event loop stays free for
        # background turns (Codex app-server semantics: one request -> many
        # notifications while the loop keeps scheduling).
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def reader() -> None:
            try:
                for line in self.stdin:
                    loop.call_soon_threadsafe(queue.put_nowait, line)
            except Exception as exc:  # noqa: BLE001 - reader 线程兜底
                log.error("stdin reader 失败: %s", exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        asyncio.create_task(asyncio.to_thread(reader))
        while True:
            line = await queue.get()
            if line is None:
                break
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as exc:
                log.warning("忽略非法 JSON-RPC 行: %s", exc)
                continue
            if "method" not in req:
                continue
            await self.dispatch(req)

    # ---------------- protocol methods ----------------
    async def rpc_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "threads": ["create", "list", "get", "rename", "archive", "fork", "delete", "prompt", "resume"],
                "approvals": ["list", "respond"],
                "models": ["list"],
                "providers": ["upsert", "delete", "test"],
                "permissions": ["list", "add", "remove"],
                "settings": ["get", "set"],
                "usage": ["stats", "daily"],
                "health": ["summary"],
                "data": ["summary"],
                "workspace": ["get", "set", "files"],
            },
            "defaults": {
                "mode": "chat",
                "model": self._resolve_provider().model,
                "provider": self._resolve_provider().name,
            },
            "workspace": str(self.workspace),
        }

    async def rpc_threads_create(self, params: dict[str, Any]) -> dict[str, Any]:
        return await self.threads.create_thread(
            title=params.get("title", "新会话"),
            parent_id=params.get("parent_id"),
            branch_point=params.get("branch_point"),
        )

    async def rpc_threads_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"threads": await self.threads.list_threads(params.get("include_archived", False))}

    async def rpc_threads_get(self, params: dict[str, Any]) -> dict[str, Any]:
        thread = await self.threads.get_thread(params["thread_id"])
        if thread is None:
            raise KeyError("会话不存在")
        return {
            **thread,
            "events": await self.threads.thread_events(params["thread_id"]),
            "tasks": await self.store.list_tasks(params["thread_id"]),
        }

    async def rpc_threads_rename(self, params: dict[str, Any]) -> dict[str, Any]:
        ok = await self.threads.rename_thread(params["thread_id"], params.get("title", ""))
        return {"ok": ok}

    async def rpc_threads_archive(self, params: dict[str, Any]) -> dict[str, Any]:
        ok = await self.threads.archive_thread(params["thread_id"], params.get("archived", True))
        return {"ok": ok}

    async def rpc_threads_fork(self, params: dict[str, Any]) -> dict[str, Any]:
        thread = await self.threads.fork_thread(params["thread_id"], params.get("branch_point"))
        if thread is None:
            raise KeyError("会话不存在")
        return thread

    async def rpc_threads_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"ok": await self.threads.delete_thread(params["thread_id"])}

    async def rpc_threads_prompt(self, params: dict[str, Any]) -> dict[str, Any]:
        assert self.threads is not None
        task = await self.threads.prompt(
            params["thread_id"],
            params.get("content", ""),
            mode=params.get("mode", "chat"),
            budgets=params.get("budgets"),
        )
        return {"task": task}

    async def rpc_threads_resume(self, params: dict[str, Any]) -> dict[str, Any]:
        """Resume an interrupted task as a new attempt on the same thread."""
        task = await self.store.get_task(params["task_id"])
        if task is None:
            raise KeyError("任务不存在")
        task = await self.threads.prompt(
            task["session_id"],
            task["content"],
            mode=task["mode"],
            budgets={**(task.get("budgets") or {}), "resumed_from": params["task_id"]},
        )
        return {"task": task}

    async def rpc_threads_regenerate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Regenerate the last turn: re-run the most recent user input."""
        events = await self.store.events(params["thread_id"])
        last_user = ""
        for ev in reversed(events):
            if ev["type"] == "item/completed":
                payload = ev["payload"]
                if payload.get("kind") == "user_message":
                    last_user = str((payload.get("payload") or {}).get("content", ""))
                    break
        if not last_user:
            raise KeyError("会话中没有可重新生成的消息")
        assert self.threads is not None
        task = await self.threads.prompt(params["thread_id"], last_user, mode=params.get("mode", "chat"))
        return {"task": task}

    async def rpc_tasks_get(self, params: dict[str, Any]) -> dict[str, Any]:
        task = await self.store.get_task(params["task_id"])
        if task is None:
            raise KeyError("任务不存在")
        return task

    async def rpc_tasks_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"tasks": await self.store.list_tasks(params.get("thread_id"))}

    async def rpc_tasks_stop(self, params: dict[str, Any]) -> dict[str, Any]:
        assert self.threads is not None
        return {"ok": await self.threads.stop(params["task_id"])}

    async def rpc_tasks_export(self, params: dict[str, Any]) -> dict[str, Any]:
        """Export a task with its full event trail (Maka-style result export)."""
        task = await self.store.get_task(params["task_id"])
        if task is None:
            raise KeyError("任务不存在")
        events = [
            dict(ev) for ev in await self.store.events(task["session_id"])
            if ev["turn_id"] == params["task_id"]
        ]
        artifacts = await self.store.list_artifacts(params["task_id"])
        return {"task": task, "events": events, "artifacts": artifacts}

    async def rpc_artifacts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"artifacts": await self.store.list_artifacts(params.get("task_id", ""))}

    async def rpc_artifacts_preview(self, params: dict[str, Any]) -> dict[str, Any]:
        from src.tools.base import safe_join

        path = str(params.get("path", ""))
        try:
            target = safe_join(self.workspace, path)
        except ValueError as exc:
            raise KeyError(str(exc))
        if not target.exists() or not target.is_file():
            raise KeyError(f"文件不存在: {path}")
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"path": path, "content": content[:20000], "truncated": len(content) > 20000}

    async def rpc_memory_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"memory": await self.store.list_memory(params.get("thread_id"), params.get("query", ""))}

    async def rpc_memory_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"ok": await self.store.delete_memory(int(params.get("id", 0)))}

    async def rpc_memory_add(self, params: dict[str, Any]) -> dict[str, Any]:
        key = str(params.get("key", "")).strip()
        value = str(params.get("value", "")).strip()
        if not key or not value:
            raise KeyError("记忆的 key 和 value 不能为空")
        return await self.store.add_memory(params.get("thread_id") or None, key, value)

    async def rpc_workspace_get(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._workspace_info()

    async def rpc_workspace_set(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.threads.has_running_tasks():
            raise KeyError("任务运行期间不能切换工作区")
        target = Path(str(params.get("path", ""))).expanduser().resolve()
        if not target.exists() or not target.is_dir():
            raise KeyError(f"工作区不存在: {target}")
        self.workspace = target
        self.threads.workspace = target
        self.threads.adapter.workspace = target
        self.settings.set_option("workspace", str(target))
        self._notify("workspace/changed", self._workspace_info())
        return self._workspace_info()

    async def rpc_workspace_files(self, params: dict[str, Any]) -> dict[str, Any]:
        from src.tools.base import safe_join

        relative = str(params.get("path", "."))
        try:
            root = safe_join(self.workspace, relative)
        except ValueError as exc:
            raise KeyError(str(exc))
        if not root.exists() or not root.is_dir():
            raise KeyError(f"目录不存在: {relative}")
        ignored = {
            ".git", ".graphcoder", ".mypy_cache", ".pytest_cache", ".ruff_cache",
            ".venv", "__pycache__", "build", "dist", "node_modules", "venv",
        }
        entries = []
        try:
            children = sorted(root.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        except PermissionError as exc:
            raise KeyError(f"目录无读取权限: {relative}") from exc
        for child in children[:500]:
            if child.name in ignored or child.name.startswith(".DS_Store"):
                continue
            try:
                stat = child.stat()
            except OSError:
                continue
            entries.append(
                {
                    "name": child.name,
                    "path": str(child.relative_to(self.workspace)),
                    "kind": "directory" if child.is_dir() else "file",
                    "size": stat.st_size,
                    "updated_at": stat.st_mtime,
                }
            )
        return {"path": relative, "entries": entries}

    def _workspace_info(self) -> dict[str, Any]:
        branch = ""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.workspace,
                capture_output=True,
                check=False,
                text=True,
                timeout=2,
            )
            branch = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        return {
            "path": str(self.workspace),
            "name": self.workspace.name,
            "branch": branch,
            "is_git": (self.workspace / ".git").exists(),
        }

    async def rpc_usage_stats(self, params: dict[str, Any]) -> dict[str, Any]:
        tasks = await self.store.list_tasks(params.get("thread_id"))
        cursor = await self.store._db_or_raise().execute(
            "SELECT COALESCE(SUM(input_tokens),0) as it, COALESCE(SUM(output_tokens),0) as ot, "
            "COALESCE(SUM(cost),0) as cost, COUNT(*) as calls FROM usage"
            + (" WHERE session_id = ?" if params.get("thread_id") else ""),
            (params["thread_id"],) if params.get("thread_id") else (),
        )
        row = await cursor.fetchone()
        if row is None:
            return {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost": 0,
                "calls": 0,
                "tasks": len(tasks),
            }
        return {
            "input_tokens": row["it"],
            "output_tokens": row["ot"],
            "total_tokens": row["it"] + row["ot"],
            "cost": row["cost"],
            "calls": row["calls"],
            "tasks": len(tasks),
        }

    async def rpc_approvals_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"approvals": self.approvals.pending()}

    async def rpc_approvals_respond(self, params: dict[str, Any]) -> dict[str, Any]:
        ok = self.approvals.respond(
            params["id"],
            bool(params.get("approved", False)),
            scope=params.get("scope", "once"),
        )
        return {"ok": ok}


    async def rpc_models_list(self, params: dict[str, Any]) -> dict[str, Any]:
        from src.providers.registry import env_provider

        env_cfg = env_provider()
        providers = [
            {**env_cfg.public(), "custom": False}
        ] if env_cfg else []
        providers += [
            {**provider.public(), "custom": False} for provider in BUILTIN_PRESETS
        ] + [
            {**provider.public(), "custom": True}
            for provider in self.settings.custom_providers()
        ]
        provider_id = params.get("id")
        if not provider_id:
            return {
                "models": providers,
                "active": self.settings.active_provider_id() or "env",
            }
        target = next((p for p in providers if p["id"] == provider_id), None)
        if target is None:
            raise KeyError("provider not found")
        if target.get("kind") != "openai-compatible":
            return {"provider": target, "models": []}

        provider_object = next(
            (
                provider
                for provider in BUILTIN_PRESETS + self.settings.custom_providers()
                if provider.id == provider_id
            ),
            None,
        )
        if provider_object is None:
            raise KeyError("provider not found")
        fetched = await self._fetch_openai_compatible_models(provider_object)
        return {"provider": target, "models": fetched}


    async def _fetch_openai_compatible_models(
        self, provider: ProviderConfig
    ) -> list[dict[str, Any]]:
        from openai import OpenAI

        client = OpenAI(
            base_url=provider.base_url or "https://api.openai.com/v1",
            api_key=provider.resolved_api_key() or "sk-not-set",
            timeout=15,
        )
        try:
            raw_models = client.models.list().data
        except Exception as exc:  # noqa: BLE001
            log.debug("抓取模型列表失败 %s: %s", provider.id, exc)
            return []
        return [{"id": m.id, "name": m.id, "model": m.id} for m in raw_models[:50]]

    async def rpc_providers_upsert(self, params: dict[str, Any]) -> dict[str, Any]:
        payload = dict(params)
        if not str(payload.get("name", "")).strip():
            raise KeyError("Provider 名称不能为空")
        if not str(payload.get("model", "")).strip():
            raise KeyError("模型名称不能为空")
        if payload.get("id") and not any(
            provider.id == payload["id"] for provider in self.settings.custom_providers()
        ):
            raise KeyError("只能编辑自定义 Provider")
        config = self.settings.upsert_provider(payload)
        return {**config.public(), "custom": True}

    async def rpc_providers_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        provider_id = str(params.get("id", ""))
        removed = self.settings.delete_provider(provider_id)
        if removed:
            config = self._resolve_provider()
            self.threads.adapter.cfg = config
            from src.providers.registry import build_provider

            self.threads.adapter.provider = build_provider(config)
        return {"ok": removed}

    async def rpc_settings_get(self, params: dict[str, Any]) -> dict[str, Any]:
        data = self.settings.load()
        data.pop("providers", None)
        data["permissions"] = await self.store.list_permissions()
        return data

    async def rpc_settings_set(self, params: dict[str, Any]) -> dict[str, Any]:
        data = self.settings.load()
        options = dict(params.get("options", {}))
        active_provider = options.pop("active_provider", None)
        if active_provider is not None:
            data["active_provider"] = str(active_provider)
        data["options"].update(options)
        self.settings.save(data)
        if active_provider is not None:
            config = self._resolve_provider()
            self.threads.adapter.cfg = config
            from src.providers.registry import build_provider

            self.threads.adapter.provider = build_provider(config)
        self.options.update(options)
        self.threads.options.update(options)
        self.threads.adapter.options.update(options)
        self.threads.adapter.refresh_tools()
        return {"ok": True}

    async def rpc_permissions_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"permissions": await self.store.list_permissions()}

    async def rpc_permissions_add(self, params: dict[str, Any]) -> dict[str, Any]:
        await self.store.add_permission(
            params.get("kind", "tool"),
            params.get("pattern", ""),
            params.get("action", "ask"),
        )
        rules = await self.store.list_permissions()
        engine = PermissionEngine()
        engine.load_rules([dict(r) for r in rules])
        self.threads.adapter.permission = engine
        return {"ok": True}

    async def rpc_permissions_remove(self, params: dict[str, Any]) -> dict[str, Any]:
        ok = await self.store.delete_permission(int(params.get("id", 0)))
        rules = await self.store.list_permissions()
        engine = PermissionEngine()
        engine.load_rules([dict(r) for r in rules])
        self.threads.adapter.permission = engine
        return {"ok": ok}

    # ---------------- settings center: probes & summaries ----------------
    async def rpc_providers_test(self, params: dict[str, Any]) -> dict[str, Any]:
        """Probe a provider connection with a minimal call."""
        from src.providers.base import ChatMessage
        from src.providers.registry import build_provider, env_provider

        provider_id = str(params.get("id", ""))
        config: ProviderConfig | None = None
        if provider_id == "env":
            config = env_provider()
        elif provider_id:
            config = next(
                (
                    p
                    for p in BUILTIN_PRESETS + self.settings.custom_providers()
                    if p.id == provider_id
                ),
                None,
            )
        if config is None:
            fields = ProviderConfig.__dataclass_fields__
            payload = {k: v for k, v in dict(params).items() if k in fields}
            if not str(payload.get("model", "")).strip():
                raise KeyError("缺少模型名称，无法测试连接")
            payload.setdefault("name", "probe")
            config = ProviderConfig(**payload)

        provider = build_provider(config)
        started = time.monotonic()

        def latency() -> int:
            return int((time.monotonic() - started) * 1000)

        try:
            if config.kind == "ollama":
                import httpx

                base = (config.base_url or "http://127.0.0.1:11434").rstrip("/")
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"{base}/api/tags")
                    resp.raise_for_status()
                return {"ok": True, "latency_ms": latency(), "detail": "Ollama 服务可达", "error": ""}
            text, _ = await asyncio.wait_for(
                provider.complete([ChatMessage(role="user", content="回复 ok")]),
                timeout=20,
            )
            return {"ok": True, "latency_ms": latency(), "detail": text[:120], "error": ""}
        except Exception as exc:  # noqa: BLE001 - 探针必须返回错误而非抛出
            return {
                "ok": False,
                "latency_ms": latency(),
                "detail": "",
                "error": f"{type(exc).__name__}: {exc}",
            }

    async def rpc_usage_daily(self, params: dict[str, Any]) -> dict[str, Any]:
        """Per-day usage for the last N days plus a per-model breakdown."""
        days = max(1, min(int(params.get("days", 14)), 90))
        db = self.store._db_or_raise()
        cursor = await db.execute(
            "SELECT date(ts, 'unixepoch', 'localtime') AS day, "
            "COALESCE(SUM(input_tokens),0) AS it, COALESCE(SUM(output_tokens),0) AS ot, "
            "COALESCE(SUM(cost),0) AS cost, COUNT(*) AS calls "
            "FROM usage WHERE ts >= ? GROUP BY day ORDER BY day",
            (time.time() - days * 86400,),
        )
        daily = [
            {
                "day": row["day"],
                "input_tokens": row["it"],
                "output_tokens": row["ot"],
                "cost": row["cost"],
                "calls": row["calls"],
            }
            for row in await cursor.fetchall()
        ]
        cursor = await db.execute(
            "SELECT COALESCE(model, '未知') AS model, COALESCE(provider, '') AS provider, "
            "COALESCE(SUM(input_tokens + output_tokens),0) AS tokens, "
            "COALESCE(SUM(cost),0) AS cost, COUNT(*) AS calls "
            "FROM usage GROUP BY model, provider ORDER BY tokens DESC LIMIT 8"
        )
        by_model = [
            {
                "model": row["model"],
                "provider": row["provider"],
                "tokens": row["tokens"],
                "cost": row["cost"],
                "calls": row["calls"],
            }
            for row in await cursor.fetchall()
        ]
        cursor = await db.execute(
            "SELECT COUNT(*) AS c FROM tasks WHERE created_at >= ?",
            (time.time() - 86400,),
        )
        row = await cursor.fetchone()
        today_tasks = row["c"] if row is not None else 0
        return {"daily": daily, "by_model": by_model, "today_tasks": today_tasks}

    async def rpc_health_summary(self, params: dict[str, Any]) -> dict[str, Any]:
        import platform

        home = graphcoder_home()
        db_path = self.store.path
        active = self._resolve_provider()
        return {
            "version": APP_VERSION,
            "protocol": PROTOCOL_VERSION,
            "python": platform.python_version(),
            "system": f"{platform.system()} {platform.release()}",
            "home": str(home),
            "db_path": str(db_path),
            "db_size": db_path.stat().st_size if db_path.exists() else 0,
            "workspace": str(self.workspace),
            "uptime_s": int(time.time() - self._started_at),
            "active_provider": {
                "id": active.id,
                "name": active.name,
                "model": active.model,
                "has_key": bool(active.resolved_api_key()),
            },
        }

    async def rpc_data_summary(self, params: dict[str, Any]) -> dict[str, Any]:
        db = self.store._db_or_raise()
        counts: dict[str, int] = {}
        for table in ("sessions", "tasks", "runtime_events", "memory", "artifacts"):
            cursor = await db.execute(f"SELECT COUNT(*) AS c FROM {table}")
            row = await cursor.fetchone()
            counts[table] = row["c"] if row is not None else 0
        db_path = self.store.path
        settings_path = self.settings.path
        return {
            "home": str(graphcoder_home()),
            "db_path": str(db_path),
            "db_size": db_path.stat().st_size if db_path.exists() else 0,
            "settings_path": str(settings_path),
            "settings_size": settings_path.stat().st_size if settings_path.exists() else 0,
            "counts": counts,
        }



async def amain(workspace: Path | None = None, home: Path | None = None) -> None:
    settings = SettingsStore(home / "settings.json" if home else None)
    saved_workspace = settings.options().get("workspace")
    ws = (workspace or (Path(saved_workspace) if saved_workspace else Path.cwd())).resolve()
    if not ws.exists() or not ws.is_dir():
        ws = Path.cwd().resolve()
    store = SqliteStore(home / "runtime.sqlite" if home else None)
    server = AppServer(store=store, settings=settings, workspace=ws)
    try:
        await server.run_forever()
    finally:
        await server.store.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="graphcoder app-server")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--home", default=None)
    args = parser.parse_args()
    home = Path(args.home) if args.home else graphcoder_home()
    workspace = Path(args.workspace) if args.workspace else None
    asyncio.run(amain(workspace, home))


if __name__ == "__main__":
    main()
