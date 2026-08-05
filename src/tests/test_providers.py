"""Provider registry and config tests."""

from __future__ import annotations

from src.providers.base import ProviderConfig
from src.providers.registry import (
    BUILTIN_PRESETS,
    build_provider,
    merge_presets,
    resolve_provider,
)


def test_builtin_presets_include_major_providers() -> None:
    ids = {p.id for p in BUILTIN_PRESETS}
    assert {"openai", "anthropic", "gemini", "ollama", "deepseek"} <= ids


def test_resolve_provider_prefers_active(monkeypatch) -> None:
    monkeypatch.delenv("API_KEY", raising=False)
    cfg = resolve_provider(active_id="gemini")
    assert cfg.id == "gemini"
    assert cfg.kind == "gemini"


def test_resolve_provider_uses_env(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "sk-test")
    monkeypatch.setenv("API_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("ACTIVE_PROVIDER", "")
    cfg = resolve_provider(active_id=None)
    assert cfg.id == "env"
    assert cfg.base_url == "https://example.com/v1"
    assert cfg.model == "test-model"


def test_public_config_masks_key() -> None:
    cfg = ProviderConfig(
        id="custom-1",
        name="Test",
        kind="openai-compatible",
        base_url="https://example.com/v1",
        api_key="secret-123",
        model="m",
    )
    public = cfg.public()
    assert public["has_key"] is True
    assert "secret-123" not in str(public)
    assert public["key_source"] == "inline"


def test_merge_presets_appends_custom() -> None:
    custom = [
        {
            "id": "my",
            "name": "My",
            "kind": "openai-compatible",
            "base_url": "http://localhost:9999/v1",
            "model": "x",
        }
    ]
    merged = merge_presets(custom)
    assert len(merged) == len(BUILTIN_PRESETS) + 1
    assert merged[-1].id == "my"


def test_build_provider_unknown_kind() -> None:
    cfg = ProviderConfig(id="x", name="x", kind="nope")
    try:
        build_provider(cfg)
        assert False, "should raise"
    except ValueError:
        pass
