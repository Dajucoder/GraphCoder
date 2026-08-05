"""User settings store (providers, active provider, workspace dir)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.providers.base import ProviderConfig
from src.utils.logging import get_logger

log = get_logger(__name__)


def graphcoder_home() -> Path:
    """Return the GraphCoder data directory (default: ~/.graphcoder)."""
    env = os.getenv("GRAPHCODER_HOME")
    if env:
        return Path(env).expanduser()
    home = Path.home() / ".graphcoder"
    try:
        home.mkdir(parents=True, exist_ok=True)
        return home
    except OSError:
        local = Path.cwd() / ".graphcoder"
        local.mkdir(parents=True, exist_ok=True)
        return local


class SettingsStore:
    """JSON-backed settings with atomic writes."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (graphcoder_home() / "settings.json")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "providers": [], "active_provider": "", "options": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            data.setdefault("providers", [])
            data.setdefault("active_provider", "")
            data.setdefault("options", {})
            data.setdefault("version", 1)
            return data
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("settings.json 读取失败，使用默认设置: %s", exc)
            return {"version": 1, "providers": [], "active_provider": "", "options": {}}

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ---- providers ----
    def custom_providers(self) -> list[ProviderConfig]:
        data = self.load()
        return [ProviderConfig(**raw) for raw in data["providers"]]

    def active_provider_id(self) -> str | None:
        data = self.load()
        return data.get("active_provider") or None

    def set_active_provider(self, provider_id: str) -> None:
        data = self.load()
        data["active_provider"] = provider_id
        self.save(data)

    def upsert_provider(self, raw: dict[str, Any]) -> ProviderConfig:
        data = self.load()
        payload_raw = dict(raw)
        if not payload_raw.get("id"):
            used_ids = {str(provider.get("id", "")) for provider in data["providers"]}
            sequence = 1
            while f"custom-{sequence}" in used_ids:
                sequence += 1
            payload_raw["id"] = f"custom-{sequence}"
        cfg = ProviderConfig(**payload_raw)
        existing = [i for i, p in enumerate(data["providers"]) if p.get("id") == cfg.id]
        payload = {
            "id": cfg.id,
            "name": cfg.name,
            "kind": cfg.kind,
            "base_url": cfg.base_url,
            "api_key": cfg.api_key,
            "api_key_env": cfg.api_key_env,
            "model": cfg.model,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "extra": cfg.extra,
        }
        if existing:
            data["providers"][existing[0]] = payload
        else:
            data["providers"].append(payload)
        self.save(data)
        return cfg

    def delete_provider(self, provider_id: str) -> bool:
        data = self.load()
        before = len(data["providers"])
        data["providers"] = [p for p in data["providers"] if p.get("id") != provider_id]
        if data.get("active_provider") == provider_id:
            data["active_provider"] = ""
        self.save(data)
        return len(data["providers"]) < before

    def options(self) -> dict[str, Any]:
        return self.load().get("options", {})

    def set_option(self, key: str, value: Any) -> None:
        data = self.load()
        data["options"][key] = value
        self.save(data)
