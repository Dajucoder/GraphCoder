"""Anthropic Claude provider (native SDK, native tool calling)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from src.providers.base import ChatMessage, ProviderConfig, ToolCall, ToolSpec


class AnthropicProvider:
    kind = "anthropic"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.client = AsyncAnthropic(
            api_key=config.resolved_api_key() or "sk-ant-not-set",
            base_url=config.base_url or None,
        )

    @staticmethod
    def _to_anthropic(messages: list[ChatMessage]) -> tuple[str, list[dict[str, Any]]]:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool":
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id or "",
                                "content": m.content,
                            }
                        ],
                    }
                )
            elif m.role == "assistant" and m.tool_calls:
                blocks: list[dict[str, Any]] = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                out.append({"role": "assistant", "content": blocks})
            else:
                out.append({"role": m.role, "content": m.content})
        return system, out

    @staticmethod
    def _to_anthropic_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        system, msgs = self._to_anthropic(messages)
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": msgs,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": True,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)

        try:
            text = ""
            tool_inputs: dict[str, dict[str, Any]] = {}
            async with self.client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                        text += event.delta.text
                        yield ("text", event.delta.text)
                    elif event.type == "content_block_start" and event.content_block.type == "tool_use":
                        tool_inputs[event.content_block.id] = {
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "raw": "",
                        }
                    elif event.type == "content_block_delta" and event.delta.type == "input_json_delta":
                        if tool_inputs:
                            list(tool_inputs.values())[-1]["raw"] += event.delta.partial_json
            for tc in tool_inputs.values():
                try:
                    arguments = json.loads(tc.get("raw") or "{}")
                except json.JSONDecodeError:
                    arguments = {"_raw": tc.get("raw", "")}
                yield ("tool_call", ToolCall(id=tc["id"], name=tc["name"], arguments=arguments))
            yield ("usage", {})
            yield ("done", text)
        except Exception as exc:  # noqa: BLE001
            yield ("error", f"{type(exc).__name__}: {exc}")

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> tuple[str, list[ToolCall]]:
        system, msgs = self._to_anthropic(messages)
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": msgs,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._to_anthropic_tools(tools)
        resp = await self.client.messages.create(**kwargs)
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        )
        calls: list[ToolCall] = []
        for b in resp.content:
            if getattr(b, "type", "") == "tool_use":
                calls.append(ToolCall(id=b.id, name=b.name, arguments=b.input or {}))
        return text, calls

