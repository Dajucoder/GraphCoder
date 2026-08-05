"""Tests for role system prompts."""

from src.agents.roles import CHAT_SYSTEM


def test_chat_system_answers_self_introduction_directly():
    assert "GraphCoder" in CHAT_SYSTEM
    assert "介绍你自己" in CHAT_SYSTEM
    assert "不调用工具" in CHAT_SYSTEM


def test_chat_system_keeps_working_rules():
    for token in ("list_files", "write_file", "apply_patch", "run_shell"):
        assert token in CHAT_SYSTEM
