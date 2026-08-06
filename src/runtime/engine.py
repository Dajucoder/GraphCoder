"""GraphCoder Agent Engine: our own provider + tool-calling loop.

Implements the same turn/item/turn/thread event projection as the v2 runtime,
but executes with the project's own multi-provider layer and tool registry
(OpenAI-compatible / Anthropic / Gemini / Ollama) plus the fine-grained
permission gate — no external agent framework dependency.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import jsonschema

from src.agents.roles import CHAT_SYSTEM
from src.providers.base import ChatMessage, ProviderConfig, ToolCall
from src.providers.registry import build_provider
from src.runtime.approvals import ApprovalHub
from src.runtime.context import shape_tool_result
from src.runtime.events import EventBus
from src.runtime.permission import ALLOW, ASK, DENY, PermissionEngine
from src.storage.sqlite_store import SqliteStore
from src.tools.base import ToolContext
from src.tools.registry import all_tools
from src.utils.logging import get_logger

log = get_logger(__name__)


class TurnResult:
    def __init__(self, text: str, messages: list[dict[str, Any]], ok: bool, error: str = "") -> None:
        self.text = text
        self.messages = messages
        self.ok = ok
        self.error = error


class AgentEngine:
    """Runs chat/build turns with the project's own providers and tools."""

    def __init__(
        self,
        provider_config: ProviderConfig,
        bus: EventBus,
        approvals: ApprovalHub,
        engine: PermissionEngine | None = None,
        options: dict[str, Any] | None = None,
        workspace: Path | None = None,
        store: SqliteStore | None = None,
    ) -> None:
        self.cfg = provider_config
        self.bus = bus
        self.approvals = approvals
        self.permission = engine or PermissionEngine()
        self.options = options or {}
        self.workspace = workspace or Path.cwd()
        self.store = store
        self.provider = build_provider(provider_config)
        self.tools = all_tools(
            enable_shell=self.options.get("enable_shell", True),
            enable_web=self.options.get("enable_web", True),
        )
        self._add_memory_tools()
        self.usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    def refresh_tools(self) -> None:
        """Rebuild the tool registry so option changes (enable_web etc.) apply."""
        self.tools = all_tools(
            enable_shell=self.options.get("enable_shell", True),
            enable_web=self.options.get("enable_web", True),
        )
        self._add_memory_tools()

    # ------------------------------------------------------------------
    async def run(
        self,
        *,
        thread_id: str,
        turn_id: str,
        user_message: str,
        conversation_history: list[dict[str, Any]] | None = None,
        role_prompt: str | None = None,
        role: str = "assistant",
        budgets: dict[str, Any] | None = None,
    ) -> TurnResult:
        """Run one turn: streamed model calls with a tool loop."""
        item_id = f"item-{uuid.uuid4().hex[:10]}"
        self.bus.emit(
            "item/started",
            thread_id=thread_id,
            turn_id=turn_id,
            item_id=item_id,
            kind="agent_message",
            role=role,
        )
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=role_prompt or CHAT_SYSTEM)
        ]
        for msg in conversation_history or []:
            r = msg.get("role")
            if r in ("user", "assistant"):
                messages.append(ChatMessage(role=r, content=str(msg.get("content", ""))))

        ctx = ToolContext(
            workspace=self.workspace,
            task_id=turn_id,
            session_id=thread_id,
            shell_approval="auto",  # engine gates before execution
            emit=None,
        )
        tool_specs = [t.spec() for t in self.tools]
        max_iterations = int(
            (budgets or {}).get("max_iterations") or self.options.get("max_iterations", 30)
        )
        text_parts: list[str] = []
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.usage["input_tokens"] = sum(len(m.content) for m in messages) // 4

        try:
            for round_no in range(max_iterations):
                calls: list[ToolCall] = []
                round_text = ""
                async for kind, payload in self.provider.stream(messages, tool_specs):
                    if kind == "text":
                        round_text += payload
                        text_parts.append(payload)
                        self.usage["output_tokens"] += len(payload) // 4
                        self.bus.emit(
                            "item/delta",
                            thread_id=thread_id,
                            turn_id=turn_id,
                            item_id=item_id,
                            delta=payload,
                        )
                    elif kind == "tool_call":
                        calls.append(payload)
                    elif kind == "error":
                        self.bus.emit("error", thread_id=thread_id, turn_id=turn_id, message=payload)
                        result = TurnResult("".join(text_parts), [], ok=False, error=payload)
                        self._finish_item(thread_id, turn_id, item_id, result.text)
                        return result

                messages.append(
                    ChatMessage(role="assistant", content=round_text, tool_calls=calls)
                )
                if not calls:
                    break

                for call in calls:
                    tool_result = await self._execute_tool(
                        thread_id=thread_id,
                        turn_id=turn_id,
                        call=call,
                        ctx=ctx,
                    )
                    messages.append(
                        ChatMessage(
                            role="tool",
                            content=tool_result,
                            name=call.name,
                            tool_call_id=call.id,
                        )
                    )

            final_text = "".join(text_parts)
            self._finish_item(thread_id, turn_id, item_id, final_text)
            return TurnResult(final_text, [m.to_dict() for m in messages], ok=True)
        except Exception as exc:
            log.exception("回合执行失败")
            self.bus.emit("error", thread_id=thread_id, turn_id=turn_id, message=str(exc))
            self._finish_item(thread_id, turn_id, item_id, "".join(text_parts))
            return TurnResult("".join(text_parts), [], ok=False, error=str(exc))

    async def _execute_tool(
        self,
        *,
        thread_id: str,
        turn_id: str,
        call: ToolCall,
        ctx: ToolContext,
    ) -> str:
        tool = next((t for t in self.tools if t.name == call.name), None)
        tool_item = f"tool-{uuid.uuid4().hex[:10]}"
        self.bus.emit(
            "item/started",
            thread_id=thread_id,
            turn_id=turn_id,
            item_id=tool_item,
            kind="tool_call",
            name=call.name,
            arguments=call.arguments,
        )
        if tool is None:
            result = f"错误: 未找到工具 {call.name}"
        else:
            try:
                jsonschema.validate(call.arguments, tool.parameters)
            except jsonschema.ValidationError as exc:
                result = f"工具参数校验失败: {exc.message}"
                self.bus.emit(
                    "item/completed",
                    thread_id=thread_id,
                    turn_id=turn_id,
                    item_id=tool_item,
                    kind="tool_call",
                    payload={"result": result, "blocked": True},
                )
                return result
            decision = self._permission_for(call.name, call.arguments)
            if decision == DENY:
                result = "工具调用被策略拒绝，不要重试"
                self.bus.emit(
                    "item/completed",
                    thread_id=thread_id,
                    turn_id=turn_id,
                    item_id=tool_item,
                    kind="tool_call",
                    payload={"result": result, "blocked": True},
                )
                return result
            if decision == ASK:
                approved, scope = await self.approvals.request(
                    kind="tool",
                    target=call.name,
                    reason=self._permission_reason(call.name, call.arguments),
                    rule_key=self._rule_key(call.name, call.arguments),
                    task_id=turn_id,
                    timeout=float(self.options.get("approval_timeout", 300)),
                )
                if not approved:
                    result = f"工具调用被用户拒绝（{scope}）"
                    self.bus.emit(
                        "item/completed",
                        thread_id=thread_id,
                        turn_id=turn_id,
                        item_id=tool_item,
                        kind="tool_call",
                        payload={"result": result, "blocked": True},
                    )
                    return result
                if scope in ("session", "always"):
                    self._remember(call.name, call.arguments, scope)
            try:
                result = await tool.handler(call.arguments, ctx)
            except Exception as exc:  # noqa: BLE001
                result = f"工具执行异常: {type(exc).__name__}: {exc}"
            if call.name in {"write_file", "apply_patch"} and self.store is not None and "错误" not in result:
                try:
                    from src.tools.base import safe_join

                    target = safe_join(self.workspace, str(call.arguments.get("path", "")))
                    if target.exists() and target.is_file():
                        await self.store.record_artifact(turn_id, str(call.arguments.get("path", "")), target.stat().st_size)
                except Exception as exc:  # noqa: BLE001
                    log.debug("记录产物失败: %s", exc)
        result = shape_tool_result(result)
        self.bus.emit(
            "item/completed",
            thread_id=thread_id,
            turn_id=turn_id,
            item_id=tool_item,
            kind="tool_call",
            payload={"result": result[:2000]},
        )
        return result

    # ------------------------------------------------------------------
    def _permission_for(self, tool_name: str, args: dict[str, Any]) -> str:
        if tool_name in {"run_shell"}:
            return self.permission.evaluate("command", str(args.get("command", ""))).action
        if tool_name in {"write_file", "apply_patch"}:
            raw = str(args.get("path", ""))
            decision = self.permission.evaluate("dir", raw)
            if decision.rule is None and raw:
                try:
                    from src.tools.base import safe_join

                    resolved = str(safe_join(self.workspace, raw))
                    resolved_decision = self.permission.evaluate("dir", resolved)
                    if resolved_decision.rule is not None:
                        decision = resolved_decision
                except ValueError:
                    pass
            return decision.action
        return self.permission.evaluate("tool", tool_name).action

    def _permission_reason(self, tool_name: str, args: dict[str, Any]) -> str:
        if tool_name == "run_shell":
            return f"需要审批执行命令: {args.get('command', '')}"
        if tool_name in {"write_file", "apply_patch"}:
            return f"需要审批写入: {args.get('path', '')}"
        return f"需要审批使用工具: {tool_name}"

    def _rule_key(self, tool_name: str, args: dict[str, Any]) -> str:
        if tool_name == "run_shell":
            return f"command:{args.get('command', '')}"
        if tool_name in {"write_file", "apply_patch"}:
            return f"dir:{args.get('path', '')}"
        return f"tool:{tool_name}"

    def _remember(self, tool_name: str, args: dict[str, Any], scope: str) -> None:
        if tool_name == "run_shell":
            self.permission.add_rule("command", str(args.get("command", "")), ALLOW, source=f"memory:{scope}")
        elif tool_name in {"write_file", "apply_patch"}:
            self.permission.add_rule("dir", str(args.get("path", "")), ALLOW, source=f"memory:{scope}")
        else:
            self.permission.add_rule("tool", tool_name, ALLOW, source=f"memory:{scope}")

    def _finish_item(self, thread_id: str, turn_id: str, item_id: str, content: str) -> None:
        self.bus.emit(
            "item/completed",
            thread_id=thread_id,
            turn_id=turn_id,
            item_id=item_id,
            kind="agent_message",
            payload={"content": content},
        )

    # ------------------------------------------------------------------
    def _add_memory_tools(self) -> None:
        from src.tools.base import Tool

        async def memory_write(args: dict, ctx: ToolContext) -> str:
            if self.store is None:
                return "错误: 记忆存储不可用"
            key = str(args.get("key", "")).strip()
            value = str(args.get("value", "")).strip()
            if not key:
                return "错误: 需要 key 参数"
            await self.store.add_memory(ctx.session_id or None, key, value)
            return f"已记住 {key}"

        async def memory_read(args: dict, ctx: ToolContext) -> str:
            if self.store is None:
                return "错误: 记忆存储不可用"
            query = str(args.get("query", args.get("key", ""))).strip()
            entries = await self.store.list_memory(ctx.session_id or None, query)
            if not entries:
                return "(没有相关记忆)"
            return "\n".join(f"- {e['key']}: {e['value']}" for e in entries[:20])

        async def memory_forget(args: dict, ctx: ToolContext) -> str:
            if self.store is None:
                return "错误: 记忆存储不可用"
            key = str(args.get("key", "")).strip()
            removed = 0
            for entry in await self.store.list_memory(ctx.session_id or None, key):
                if entry["key"] == key and await self.store.delete_memory(entry["id"]):
                    removed += 1
            return f"已遗忘 {removed} 条记忆" if removed else f"未找到记忆: {key}"

        self.tools += [
            Tool(
                name="memory_write",
                description="写入一条长期记忆（key/value），供后续对话使用。",
                parameters={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "记忆键"},
                        "value": {"type": "string", "description": "记忆内容"},
                    },
                    "required": ["key", "value"],
                },
                handler=memory_write,
            ),
            Tool(
                name="memory_read",
                description="读取本会话的长期记忆，可按关键词过滤。",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                    "required": [],
                },
                handler=memory_read,
            ),
            Tool(
                name="memory_forget",
                description="删除指定 key 的记忆。",
                parameters={
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"],
                },
                handler=memory_forget,
            ),
        ]
