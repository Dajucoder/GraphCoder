"""Shell execution tool with approval gate."""

from __future__ import annotations

import asyncio

from src.tools.approval import ApprovalManager
from src.tools.base import Tool, ToolContext

DANGEROUS_PATTERNS = (
    "rm -rf /",
    "rm -rf ~",
    "mkfs",
    "dd if=",
    ":(){",
    "> /dev/sda",
    "git push --force",
)


def _needs_approval(command: str) -> bool:
    compact = " ".join(command.split())
    return any(p in compact for p in DANGEROUS_PATTERNS)


async def _run_shell(args: dict, ctx: ToolContext) -> str:
    command = str(args.get("command", "")).strip()
    if not command:
        return "错误: 缺少 command 参数"

    timeout = float(args.get("timeout", 120))
    dangerous = _needs_approval(command)

    if dangerous or ctx.shell_approval == "ask":
        if ctx.shell_approval == "never":
            return "Shell 执行已被策略禁用 (shell_approval=never)"
        manager: ApprovalManager = ctx.approvals
        if manager is not None:
            if ctx.emit:
                ctx.emit("status", {"message": f"⏳ 等待命令审批: {command}"})
            approved = await manager.request(command, ctx.task_id)
            if not approved:
                return f"命令已被拒绝（用户未批准）: {command}"

    if ctx.emit:
        ctx.emit("status", {"message": f"$ {command}"})
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=ctx.workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        stdout = output[0].decode("utf-8", errors="replace") if output[0] else ""
        truncated = ""
        if len(stdout) > 8000:
            stdout = stdout[:8000]
            truncated = f"\n... [输出已截断，共 {len(output[0])} 字节]"
        status = f"退出码: {proc.returncode}"
        if proc.returncode != 0:
            status += " (命令执行失败)"
        return f"{status}\n{stdout}{truncated}" if stdout else status
    except asyncio.TimeoutError:
        return f"错误: 命令执行超时（{timeout}s）: {command}"
    except Exception as exc:  # noqa: BLE001
        return f"错误: 命令执行失败: {type(exc).__name__}: {exc}"


def shell_tools() -> list[Tool]:
    return [
        Tool(
            name="run_shell",
            description=(
                "在工作区执行 Shell 命令（macOS/Linux/Windows），返回 stdout/stderr。"
                "危险命令或需要时会被要求人工审批。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"},
                    "timeout": {"type": "integer", "description": "超时秒数", "default": 120},
                },
                "required": ["command"],
            },
            handler=_run_shell,
        )
    ]
