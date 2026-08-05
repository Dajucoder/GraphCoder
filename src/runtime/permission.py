"""Fine-grained permission engine (allow / ask / deny).

Rules are evaluated by kind: ``command`` (shell command patterns),
``tool`` (tool name), ``dir`` (path prefix). The most specific matching
rule wins; a deny beats allow at equal specificity; ask is the default for
unknown targets when ``default_ask`` is on.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Any

ALLOW = "allow"
ASK = "ask"
DENY = "deny"

DEFAULT_POLICY_RULES: list[dict[str, Any]] = [
    {"kind": "command", "pattern": "git status*", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "git diff*", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "git log*", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "ls*", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "pwd", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "cat *", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "python -m pytest*", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "pytest*", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "npm test*", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "python -m unittest*", "action": "allow", "source": "builtin"},
    {"kind": "command", "pattern": "rm -rf /*", "action": "deny", "source": "builtin"},
    {"kind": "command", "pattern": "rm -rf ~*", "action": "deny", "source": "builtin"},
    {"kind": "command", "pattern": "mkfs*", "action": "deny", "source": "builtin"},
    {"kind": "command", "pattern": "dd if=*", "action": "deny", "source": "builtin"},
    {"kind": "command", "pattern": ":(){*", "action": "deny", "source": "builtin"},
    {"kind": "command", "pattern": "git push --force*", "action": "deny", "source": "builtin"},
]


@dataclass
class PermissionDecision:
    action: str
    rule: dict[str, Any] | None = None
    reason: str = ""


class PermissionEngine:
    """Holds rules in memory; persists policy rules via the store."""

    def __init__(self, default_ask: bool = True) -> None:
        self.default_ask = default_ask
        self._rules: list[dict[str, Any]] = list(DEFAULT_POLICY_RULES)

    def load_rules(self, rules: list[dict[str, Any]]) -> None:
        """Replace in-memory rules (call with SQLite permissions at turn start)."""
        self._rules = list(DEFAULT_POLICY_RULES) + list(rules)

    def add_rule(self, kind: str, pattern: str, action: str, source: str = "memory") -> None:
        self._rules.append({"kind": kind, "pattern": pattern, "action": action, "source": source})

    def evaluate(self, kind: str, target: str) -> PermissionDecision:
        """Evaluate the most specific matching rule.

        Specificity: exact pattern > prefix pattern > wildcard; deny beats
        allow at equal specificity.
        """
        best: dict[str, Any] | None = None
        best_specificity = -1
        best_rank = {"allow": 0, "ask": 1, "deny": 2}
        for rule in self._rules:
            if rule.get("kind") != kind:
                continue
            pattern = str(rule.get("pattern", ""))
            if not _matches(kind, pattern, target):
                continue
            specificity = _specificity(pattern)
            rank = best_rank.get(rule.get("action", "ask"), 0)
            if (
                best is None
                or specificity > best_specificity
                or (specificity == best_specificity and rank > best_rank.get(best.get("action", "ask"), 0))
            ):
                best = rule
                best_specificity = specificity
        if best is not None:
            action = best.get("action", ASK)
            reason = f"策略[{best.get('source', 'policy')}]: {best.get('pattern')}"
            return PermissionDecision(action=action, rule=best, reason=reason)
        if self.default_ask:
            return PermissionDecision(action=ASK, reason="无匹配策略，默认询问")
        return PermissionDecision(action=ALLOW, reason="无匹配策略，默认放行")

    def as_policy_dicts(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._rules if r.get("source") != "builtin"]


def _matches(kind: str, pattern: str, target: str) -> bool:
    if kind == "dir":
        return target.startswith(pattern)
    # command / tool: fnmatch, case-insensitive for commands
    if kind == "command":
        return fnmatch.fnmatch(target.lower(), pattern.lower()) or target.lower().startswith(
            pattern.lower().rstrip("*")
        )
    return fnmatch.fnmatch(target, pattern)


def _specificity(pattern: str) -> int:
    """Rank specificity: exact > prefix-with-* at end > wildcard > bare *."""
    if pattern == "*":
        return 0
    if "*" not in pattern:
        return 3
    if pattern.endswith("*") and "*" not in pattern[:-1]:
        return 2
    return 1
