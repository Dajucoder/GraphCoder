"""Ollama local provider (native SDK)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ollama import AsyncClient

from src.providers.base import ChatMessage, ProviderConfig, ToolCall, ToolSpec


class OllamaProvider:
    kind = "ollama"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.client = AsyncClient(host=config.base_url or "http://127.0.0.1:11434")

    @staticmethod
    def _to_ollama(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "tool":
                out.append({"role": "tool", "content": m.content, "name": m.name})
            elif m.role == "assistant" and m.tool_calls:
                out.append(
                    {
                        "role": "assistant",
                        "content": m.content,
                        "tool_calls": [
                            {"function": {"name": tc.name, "arguments": tc.arguments}}
                            for tc in m.tool_calls
                        ],
                    }
                )
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": self._to_ollama(messages),
            "stream": True,
        }
        if tools:
            kwargs["tools"] = [t.to_openai() for t in tools]
        try:
            text = ""
            async for chunk in await self.client.chat(**kwargs):
                msg = chunk.get("message") or {}
                if msg.get("content"):
                    text += msg["content"]
                    yield ("text", msg["content"])
                for tc in msg.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    yield (
                        "tool_call",
                        ToolCall(
                            id=f"ollama-{len(text)}",
                            name=fn.get("name", ""),
                            arguments=fn.get("arguments", {}) or {},
                        ),
                    )
            yield ("usage", {})
            yield ("done", text)
        except Exception as exc:  # noqa: BLE001
            yield ("error", f"{type(exc).__name__}: {exc}")

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> tuple[str, list[ToolCall]]:
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": self._to_ollama(messages),
            "stream": False,
        }
        if tools:
            kwargs["tools"] = [t.to_openai() for t in tools]
        resp = await self.client.chat(**kwargs)
        msg = resp.get("message") or {}
        calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            calls.append(ToolCall(id=f"ollama-{len(calls)}", name=fn.get("name", ""), arguments=fn.get("arguments", {}) or {}))
        return msg.get("content", ""), calls
