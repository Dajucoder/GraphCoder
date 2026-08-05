"""Unified provider abstraction.

Every provider (OpenAI-compatible, Anthropic, Gemini, Ollama, custom) exposes
the same async ``stream()`` / ``complete()`` interface so the rest of the
system is provider-agnostic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ChatMessage:
    """A single chat message in a provider-agnostic format."""

    role: Role
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "name": self.name,
            "tool_call_id": self.tool_call_id,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
        }


@dataclass
class ToolCall:
    """A structured request from the model to invoke a tool."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass
class ToolSpec:
    """JSON-schema description of a callable tool."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Any = None

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""

    name: str
    kind: str  # openai-compatible | anthropic | gemini | ollama
    id: str = ""
    base_url: str | None = None
    api_key: str | None = None
    api_key_env: str | None = None  # read the key from this env var instead
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 8192
    extra: dict[str, Any] = field(default_factory=dict)

    def resolved_api_key(self) -> str | None:
        """Return the actual key, resolving env-var references if needed."""
        if self.api_key_env:
            return __import__("os").getenv(self.api_key_env)
        return self.api_key

    def public(self) -> dict[str, Any]:
        """Safe representation without exposing secrets."""
        key = self.resolved_api_key() or self.api_key
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "has_key": bool(key),
            "key_source": "env" if self.api_key_env else ("inline" if key else "none"),
            "extra": self.extra,
        }


class Provider(Protocol):
    """Async chat interface implemented by every provider."""

    config: ProviderConfig

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """Yield ``("text", str)``, ``("tool_call", ToolCall)``, ``("usage", dict)``, ``("done", str)`` or ``("error", str)``."""
        ...

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> tuple[str, list[ToolCall]]:
        """Non-streaming call returning ``(text, tool_calls)``."""
        ...


class ProviderError(RuntimeError):
    """Raised when a provider call fails."""
