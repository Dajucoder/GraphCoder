"""Interactive chat runner with a native tool-calling loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.roles import CHAT_SYSTEM
from src.core.events import EventSink
from src.providers.base import ChatMessage, ProviderConfig, ToolCall
from src.tools.base import Tool, ToolContext
from src.utils.logging import get_logger

log = get_logger(__name__)

MAX_TOOL_ROUNDS = 12


def messages_from_history(history: list[dict[str, Any]]) -> list[ChatMessage]:
    """Convert persisted history records back to ChatMessage objects."""
    out: list[ChatMessage] = []
    for item in history:
        role = item.get("role")
        if role == "system":
            continue
        out.append(
            ChatMessage(
                role=role if role in ("user", "assistant", "tool") else "user",  # type: ignore[arg-type]
                content=item.get("content", ""),
                name=item.get("name"),
                tool_call_id=item.get("tool_call_id"),
                tool_calls=[
                    ToolCall(
                        id=tc["id"], name=tc["name"], arguments=tc.get("arguments", {})
                    )
                    for tc in item.get("tool_calls", [])
                ],
            )
        )
    return out


async def run_chat(
    *,
    history: list[dict[str, Any]],
    user_message: str,
    provider_config: ProviderConfig,
    provider,
    tools: list[Tool],
    sink: EventSink,
    workspace: Path,
    ctx: ToolContext,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> tuple[str, list[dict[str, Any]]]:
    """Run one chat turn. Returns (final_text, full_message_history)."""
    sink.emit("status", message="思考中...")
    messages = [ChatMessage(role="system", content=CHAT_SYSTEM)]
    messages += messages_from_history(history)
    messages.append(ChatMessage(role="user", content=user_message))

    tool_specs = [t.spec() for t in tools]
    text_parts: list[str] = []

    for round_no in range(max_rounds):
        sink.emit("status", message=f"模型调用（第 {round_no + 1} 轮）...")
        calls: list[Any] = []
        text = ""
        async for kind, payload in provider.stream(messages, tool_specs):
            if kind == "text":
                text += payload
                sink.emit("text", delta=payload)
            elif kind == "tool_call":
                calls.append(payload)
            elif kind == "error":
                sink.emit("error", message=payload)
                return text or payload, []

        assistant = ChatMessage(
            role="assistant",
            content=text,
            tool_calls=calls,
        )
        messages.append(assistant)

        if not calls:
            text_parts.append(text)
            break

        for call in calls:
            tool = next((t for t in tools if t.name == call.name), None)
            sink.emit("tool_call", id=call.id, name=call.name, arguments=call.arguments)
            if tool is None:
                result = f"错误: 未找到工具 {call.name}"
            else:
                try:
                    result = await tool.handler(call.arguments, ctx)
                except Exception as exc:  # noqa: BLE001
                    result = f"工具执行异常: {type(exc).__name__}: {exc}"
            sink.emit("tool_result", id=call.id, name=call.name, result=result)
            messages.append(
                ChatMessage(
                    role="tool",
                    content=result,
                    name=call.name,
                    tool_call_id=call.id,
                )
            )

    final_text = "\n\n".join(p for p in text_parts if p)
    sink.emit("assistant_message", content=final_text)
    sink.emit("done", content=final_text)
    return final_text, [m.to_dict() for m in messages if m.role != "system"]
