"""Google Gemini provider (native SDK, native function calling)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

from src.providers.base import ChatMessage, ProviderConfig, ToolCall, ToolSpec


class GeminiProvider:
    kind = "gemini"

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self.client = genai.Client(api_key=config.resolved_api_key() or "not-set")

    @staticmethod
    def _to_gemini(messages: list[ChatMessage]) -> tuple[str | None, list[types.Content]]:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        contents: list[types.Content] = []
        for m in messages:
            if m.role == "system":
                continue
            if m.role == "tool":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=m.name or "tool",
                                    response={"result": m.content},
                                )
                            )
                        ],
                    )
                )
            elif m.role == "assistant" and m.tool_calls:
                parts: list[types.Part] = []
                if m.content:
                    parts.append(types.Part(text=m.content))
                for tc in m.tool_calls:
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                name=tc.name, args=tc.arguments
                            )
                        )
                    )
                contents.append(types.Content(role="model", parts=parts))
            else:
                contents.append(types.Content(role=m.role, parts=[types.Part(text=m.content)]))
        return system or None, contents

    @staticmethod
    def _to_gemini_tools(tools: list[ToolSpec]) -> list[types.Tool]:
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=t.name,
                        description=t.description,
                        parameters=types.Schema.model_validate(t.parameters),
                    )
                    for t in tools
                ]
            )
        ]

    async def stream(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        system, contents = self._to_gemini(messages)
        config: dict[str, Any] = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
        }
        if system:
            config["system_instruction"] = system
        if tools:
            config["tools"] = self._to_gemini_tools(tools)
        try:
            response = await self.client.aio.models.generate_content_stream(
                model=self.config.model,
                contents=contents,
                config=types.GenerateContentConfig(**config),
            )
            text = ""
            calls: list[ToolCall] = []
            async for chunk in response:
                if not chunk.candidates or not chunk.candidates[0].content:
                    continue
                parts = chunk.candidates[0].content.parts or []
                for part in parts:
                    if part.text:
                        text += part.text
                        yield ("text", part.text)
                    if part.function_call:
                        calls.append(
                            ToolCall(
                                id=f"fc-{len(calls)}",
                                name=part.function_call.name or "",
                                arguments=dict(part.function_call.args or {}),
                            )
                        )
            for tc in calls:
                yield ("tool_call", tc)
            yield ("usage", {})
            yield ("done", text)
        except Exception as exc:  # noqa: BLE001
            yield ("error", f"{type(exc).__name__}: {exc}")

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolSpec] | None = None,
    ) -> tuple[str, list[ToolCall]]:
        system, contents = self._to_gemini(messages)
        config: dict[str, Any] = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
        }
        if system:
            config["system_instruction"] = system
        if tools:
            config["tools"] = self._to_gemini_tools(tools)
        resp = await self.client.aio.models.generate_content(
            model=self.config.model,
            contents=contents,
            config=types.GenerateContentConfig(**config),
        )
        text = resp.text or ""
        calls: list[ToolCall] = []
        if resp.candidates and resp.candidates[0].content:
            for part in resp.candidates[0].content.parts or []:
                if part.function_call:
                    calls.append(
                        ToolCall(
                            id=f"fc-{len(calls)}",
                            name=part.function_call.name or "",
                            arguments=dict(part.function_call.args or {}),
                        )
                    )
        return text, calls
