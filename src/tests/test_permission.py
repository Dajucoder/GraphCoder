"""Permission engine tests."""

from __future__ import annotations

from src.runtime.permission import ALLOW, ASK, DENY, PermissionEngine


def _engine() -> PermissionEngine:
    engine = PermissionEngine(default_ask=True)
    engine.add_rule("command", "git push*", ALLOW, source="test")
    engine.add_rule("command", "rm -rf /*", DENY, source="test")
    engine.add_rule("command", "rm *", ASK, source="test")
    engine.add_rule("tool", "write_file", ALLOW, source="test")
    engine.add_rule("dir", "src/", ALLOW, source="test")
    return engine


def test_allow_command() -> None:
    assert _engine().evaluate("command", "git push origin main").action == ALLOW


def test_deny_beats_ask_at_same_specificity() -> None:
    decision = _engine().evaluate("command", "rm -rf /")
    assert decision.action == DENY


def test_ask_default() -> None:
    assert _engine().evaluate("command", "curl http://x").action == ASK


def test_specific_deny_beats_broad_allow() -> None:
    engine = PermissionEngine(default_ask=True)
    engine.add_rule("command", "python *", ALLOW, source="t")
    engine.add_rule("command", "python -m pip install --user *", DENY, source="t")
    assert engine.evaluate("command", "python -m pip install --user x").action == DENY
    assert engine.evaluate("command", "python script.py").action == ALLOW


def test_tool_and_dir_rules() -> None:
    engine = _engine()
    assert engine.evaluate("tool", "write_file").action == ALLOW
    assert engine.evaluate("dir", "src/app.py").action == ALLOW
    assert engine.evaluate("dir", "docs/x.md").action == ASK


def test_memory_rule_added_and_used() -> None:
    engine = PermissionEngine(default_ask=True)
    engine.add_rule("command", "ls -la", ALLOW, source="memory:always")
    assert engine.evaluate("command", "ls -la").action == ALLOW
