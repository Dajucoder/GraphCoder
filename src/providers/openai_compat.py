"""OpenAI-compatible provider (OpenAI, DeepSeek, Moonshot, Qwen, vLLM, custom...)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, OpenAIError

from src.providers.base import ChatMessage, ProviderConfig, ToolCall, ToolSpec


class OpenAICompatProvider:
    """Provider for any OpenAI-compatible chat completions endpoint."""

    kind = "openai-compatible"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.client = AsyncOpenAI(
            base_url=config.base_url or "https://api.openai.com/v1",
            api_key=config.resolved_api_key() or "sk-not-set",
            timeout=config.extra.get("timeout", 120),
            max_retries=config.extra.get("max_retries", 2),
            default_headers=config.extra.get("headers"),
        )

    @staticmethod
    def _to_openai(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "content": m.content,
                        "tool_call_id": m.tool_call_id,
                    }
                )
            elif m.role == "assistant" and m.tool_calls:
                out.append(
                    {
                        "role": "assistant",
                        "content": m.content or None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                                },
                            }
                            for tc in m.tool_calls
                        ],
                    }
                )
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    def _params(
        self, messages: list[ChatMessage], tools: list[ToolSpec] | None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.config.model,
            "messages": self._to_openai(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "stream": True,
        }
        if tools:
            params["tools"] = [t.to_openai() for t in tools]
        return params

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        try:
            stream = await self.client.chat.completions.create(**self._params(messages, tools))
        except OpenAIError as exc:
            yield ("error", f"{type(exc).__name__}: {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - surface provider errors to clients
            yield ("error", f"{type(exc).__name__}: {exc}")
            return

        text = ""
        slots: dict[int, dict[str, str]] = {}
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                text += delta.content
                yield ("text", delta.content)
            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    slot = slots.setdefault(tc.index or 0, {"id": "", "name": "", "arguments": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments
        if slots:
            for slot in slots.values():
                try:
                    args = json.loads(slot["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": slot["arguments"]}
                yield ("tool_call", ToolCall(id=slot["id"], name=slot["name"], arguments=args))
        yield ("usage", {})
        yield ("done", text)

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> tuple[str, list[ToolCall]]:
        params = self._params(messages, tools)
        params["stream"] = False
        resp = await self.client.chat.completions.create(**params)
        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
        return msg.content or "", calls
