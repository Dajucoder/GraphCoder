"""LangGraph multi-agent build pipeline: PM -> Architect -> Developer -> Reviewer -> QA."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.roles import (
    ARCHITECT_SYSTEM,
    DEVELOPER_SYSTEM,
    PM_SYSTEM,
    QA_SYSTEM,
    REVIEWER_SYSTEM,
)
from src.core.events import EventSink
from src.core.state import GraphState
from src.providers.base import ChatMessage
from src.tools.base import Tool, ToolContext

MAX_ATTEMPTS_DEFAULT = 3
MAX_DEV_TOOL_ROUNDS = 15


async def _complete(
    provider,
    system: str,
    user: str,
    sink: EventSink,
    label: str,
) -> str:
    sink.emit("status", message=f"🧠 {label} 正在分析...")
    text = ""
    async for kind, payload in provider.stream(
        [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ]
    ):
        if kind == "text":
            text += payload
            sink.emit("text", delta=payload, agent=label)
        elif kind == "error":
            sink.emit("error", message=payload, agent=label)
            raise RuntimeError(payload)
    return text


async def _pm_node(state: GraphState, provider, sink: EventSink) -> dict[str, Any]:
    prd = await _complete(provider, PM_SYSTEM, state["request"], sink, "PM")
    return {"prd": prd}


async def _architect_node(state: GraphState, provider, sink: EventSink) -> dict[str, Any]:
    arch = await _complete(
        provider,
        ARCHITECT_SYSTEM,
        f"# 用户需求\n{state['request']}\n\n# PRD\n{state['prd']}",
        sink,
        "架构师",
    )
    return {"architecture": arch}


async def _developer_node(
    state: GraphState,
    provider,
    sink: EventSink,
    tools: list[Tool],
    ctx: ToolContext,
) -> dict[str, Any]:
    feedback = ""
    if state.get("review"):
        feedback = f"\n\n# 上一轮审查意见（必须修复）\n{state['review']}\n\n# 上一轮 QA 意见\n{state.get('qa_result', '')}"
    user = (
        f"# 用户需求\n{state['request']}\n\n"
        f"# 架构设计\n{state['architecture']}\n\n"
        f"# 工作区\n{ctx.workspace}{feedback}\n\n"
        "请开始实现。完成后汇报：实现摘要、文件清单、验证结果。"
    )
    sink.emit("status", message="🧑‍💻 Developer 开始编码...")
    messages = [
        ChatMessage(role="system", content=DEVELOPER_SYSTEM),
        ChatMessage(role="user", content=user),
    ]
    tool_specs = [t.spec() for t in tools]
    text = ""
    for _ in range(MAX_DEV_TOOL_ROUNDS):
        calls: list[Any] = []
        round_text = ""
        async for kind, payload in provider.stream(messages, tool_specs):
            if kind == "text":
                round_text += payload
                text += payload
                sink.emit("text", delta=payload, agent="Developer")
            elif kind == "tool_call":
                calls.append(payload)
            elif kind == "error":
                sink.emit("error", message=payload, agent="Developer")
                raise RuntimeError(payload)
        messages.append(
            ChatMessage(role="assistant", content=round_text, tool_calls=calls)
        )
        if not calls:
            break
        for call in calls:
            tool = next((t for t in tools if t.name == call.name), None)
            sink.emit("tool_call", name=call.name, arguments=call.arguments, agent="Developer")
            if tool is None:
                result = f"错误: 未找到工具 {call.name}"
            else:
                try:
                    result = await tool.handler(call.arguments, ctx)
                except Exception as exc:  # noqa: BLE001
                    result = f"工具执行异常: {type(exc).__name__}: {exc}"
            sink.emit("tool_result", name=call.name, result=result)
            messages.append(
                ChatMessage(role="tool", content=result, name=call.name, tool_call_id=call.id)
            )
    return {"implementation": text}


async def _reviewer_node(state: GraphState, provider, sink: EventSink) -> dict[str, Any]:
    review = await _complete(
        provider,
        REVIEWER_SYSTEM,
        f"# 用户需求\n{state['request']}\n\n# 架构设计\n{state['architecture']}\n\n# 实现\n{state['implementation']}",
        sink,
        "审查员",
    )
    return {"review": review}


async def _qa_node(state: GraphState, provider, sink: EventSink) -> dict[str, Any]:
    qa = await _complete(
        provider,
        QA_SYSTEM,
        f"# 实现\n{state['implementation']}\n\n# 审查意见\n{state.get('review', '')}",
        sink,
        "QA",
    )
    match = re.search(r"结论[:：]\s*(PASS|FAIL)", qa.upper())
    qa_pass = match.group(1) == "PASS" if match else "FAIL" not in qa.upper()
    return {
        "qa_result": qa,
        "qa_pass": qa_pass,
        "attempts": state.get("attempts", 0) + 1,
    }


def build_graph(
    *,
    provider,
    tools: list[Tool],
    workspace: Path,
    approvals: Any = None,
    max_attempts: int = MAX_ATTEMPTS_DEFAULT,
    event_emitter=None,
):
    """Build the LangGraph pipeline with loop-back on QA failure."""

    def make_sink(task_id: str) -> EventSink:
        sink = EventSink()

        def forward(kind: str, payload: dict[str, Any]) -> None:
            if event_emitter is not None:
                event_emitter(kind, {"task_id": task_id, **payload})

        original = sink.emit

        def emit(kind: str, **payload: Any) -> None:
            original(kind, **payload)
            forward(kind, payload)

        sink.emit = emit  # type: ignore[method-assign]
        return sink

    async def pm_node(state: GraphState) -> dict[str, Any]:
        sink = make_sink(state["task_id"])
        return await _pm_node(state, provider, sink)

    async def architect_node(state: GraphState) -> dict[str, Any]:
        sink = make_sink(state["task_id"])
        return await _architect_node(state, provider, sink)

    async def developer_node(state: GraphState) -> dict[str, Any]:
        sink = make_sink(state["task_id"])
        ctx = ToolContext(
            workspace=workspace,
            task_id=state["task_id"],
            session_id=state.get("session_id", ""),
            emit=lambda kind, payload: event_emitter(kind, payload) if event_emitter else None,
            approvals=approvals,
        )
        return await _developer_node(state, provider, sink, tools, ctx)

    async def reviewer_node(state: GraphState) -> dict[str, Any]:
        sink = make_sink(state["task_id"])
        return await _reviewer_node(state, provider, sink)

    async def qa_node(state: GraphState) -> dict[str, Any]:
        sink = make_sink(state["task_id"])
        return await _qa_node(state, provider, sink)

    def route_after_qa(state: GraphState) -> str:
        attempts = state.get("attempts", 1)
        if state.get("qa_pass") or attempts >= state.get("max_attempts", max_attempts):
            return "done"
        return "developer"

    builder = StateGraph(GraphState)
    builder.add_node("pm", pm_node)
    builder.add_node("architect", architect_node)
    builder.add_node("developer", developer_node)
    builder.add_node("reviewer", reviewer_node)
    builder.add_node("qa", qa_node)
    builder.add_edge(START, "pm")
    builder.add_edge("pm", "architect")
    builder.add_edge("architect", "developer")
    builder.add_edge("developer", "reviewer")
    builder.add_edge("reviewer", "qa")
    builder.add_conditional_edges(
        "qa",
        route_after_qa,
        {"developer": "developer", "done": END},
    )
    return builder.compile()
