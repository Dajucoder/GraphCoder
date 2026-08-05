"""GraphCoder CLI: interactive chat, one-shot build, server, provider & session management."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from src.core.chat import run_chat
from src.core.events import EventSink
from src.core.graph import build_graph
from src.data.store import Store
from src.providers.base import ChatMessage
from src.providers.registry import BUILTIN_PRESETS, build_provider, resolve_provider
from src.tools.approval import ApprovalManager
from src.tools.base import ToolContext
from src.tools.mcp_client import McpManager
from src.tools.registry import all_tools
from src.utils.settings import SettingsStore

console = Console()


class CliApprovalManager(ApprovalManager):
    """Approval manager that prompts the user directly in the terminal."""

    async def request(self, command: str, task_id: str, timeout: float = 300.0) -> bool:
        console.print(f"\n[bold yellow]⚠ 命令需要审批:[/bold yellow] {command}")
        answer = console.input("[bold]是否允许执行？(y/N) [/bold]").strip().lower()
        return answer in {"y", "yes"}


def _build_tool_ctx(
    task_id: str,
    workspace: Path,
    approvals: ApprovalManager,
    settings: SettingsStore,
) -> ToolContext:
    return ToolContext(
        workspace=workspace,
        task_id=task_id,
        approvals=approvals,
        shell_approval=settings.options().get("shell_approval", "ask"),
        emit=lambda kind, payload: None,
    )


def _make_sink():
    sink = EventSink()

    def emit(kind: str, **payload: Any) -> None:
        if kind == "status":
            console.print(f"[dim]• {payload.get('message', '')}[/dim]")
        elif kind == "tool_call":
            name = payload.get("name", "")
            args = payload.get("arguments", {})
            console.print(
                Panel(
                    f"[bold cyan]🔧 {name}[/bold cyan]\n{json.dumps(args, ensure_ascii=False)[:600]}",
                    title="工具调用",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )
        elif kind == "tool_result":
            result = payload.get("result", "")
            console.print(Panel(result[:1500], title="工具结果", border_style="blue", padding=(0, 1)))
        elif kind == "error":
            console.print(f"[bold red]错误:[/bold red] {payload.get('message', '')}")
        elif kind == "text":
            console.print(payload.get("delta", ""), end="")

    sink.emit = emit  # type: ignore[method-assign]
    return sink


async def _do_chat(
    user_message: str,
    *,
    workspace: Path,
    settings: SettingsStore,
    approvals: ApprovalManager,
) -> str:
    cfg = resolve_provider(settings.custom_providers(), settings.active_provider_id())
    provider = build_provider(cfg)
    tools = all_tools(
        enable_shell=settings.options().get("enable_shell", True),
        enable_web=settings.options().get("enable_web", True),
        mcp=McpManager(settings.load().get("mcp_servers", [])),
    )
    sink = _make_sink()
    text, _ = await run_chat(
        history=[],
        user_message=user_message,
        provider_config=cfg,
        provider=provider,
        tools=tools,
        sink=sink,
        workspace=workspace,
        ctx=_build_tool_ctx("cli", workspace, approvals, settings),
    )
    return text


async def _do_build(
    request: str,
    *,
    workspace: Path,
    settings: SettingsStore,
    approvals: ApprovalManager,
) -> str:
    cfg = resolve_provider(settings.custom_providers(), settings.active_provider_id())
    provider = build_provider(cfg)
    tools = all_tools(
        enable_shell=settings.options().get("enable_shell", True),
        enable_web=settings.options().get("enable_web", True),
        mcp=McpManager(settings.load().get("mcp_servers", [])),
    )
    graph = build_graph(
        provider=provider,
        tools=tools,
        workspace=workspace,
        approvals=approvals,
        max_attempts=int(settings.options().get("max_attempts", 3)),
        event_emitter=lambda kind, payload: None,
    )
    final_state: dict[str, Any] = {}
    async for snapshot in graph.astream(
        {
            "request": request,
            "session_id": "cli",
            "task_id": "build",
            "attempts": 0,
            "max_attempts": int(settings.options().get("max_attempts", 3)),
            "events": [],
            "history": [],
        },
        config={"recursion_limit": 100},
        stream_mode="values",
    ):
        final_state = snapshot
    qa = final_state.get("qa_result", "")
    impl = final_state.get("implementation", "")
    console.print()
    console.print(Panel(Markdown(f"## QA 结论\n\n{qa}"), title="QA", border_style="magenta"))
    console.print(Panel(Markdown(f"## 实现摘要\n\n{impl[:3000]}"), title="实现", border_style="green"))
    return qa


def cmd_chat(args: argparse.Namespace) -> None:
    settings = SettingsStore()
    approvals = CliApprovalManager()
    console.print(Panel(f"[bold]GraphCoder 交互模式[/bold]\n工作区: {Path.cwd()}\n输入 exit 或 Ctrl+C 退出", border_style="green"))
    while True:
        try:
            prompt = console.input("[bold green]你 > [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n再见！")
            return
        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit", "/exit"}:
            return
        if prompt.startswith("/build "):
            console.print("[dim]构建模式：运行多 Agent 流水线...[/dim]")
            asyncio.run(_do_build(prompt[7:].strip(), workspace=Path.cwd(), settings=settings, approvals=approvals))
            continue
        console.print("[dim]思考中...[/dim]")
        try:
            asyncio.run(_do_chat(prompt, workspace=Path.cwd(), settings=settings, approvals=approvals))
            console.print()
        except Exception as exc:  # noqa: BLE001
            console.print(f"[bold red]错误:[/bold red] {type(exc).__name__}: {exc}")


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    from src.api.server import create_app

    app = create_app(workspace=Path.cwd())
    console.print(f"[bold green]GraphCoder API 服务[/bold green] http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


def cmd_tui(args: argparse.Namespace) -> None:
    from src.cli.tui import run_tui

    run_tui(workspace=Path.cwd(), thread_id=getattr(args, "thread_id", None))


def cmd_app_server(args: argparse.Namespace) -> None:
    """Launch the stdio app-server (JSON-RPC over stdio)."""
    from src.api.app_server import main as app_server_main

    sys.argv = [sys.argv[0], "--workspace", str(Path.cwd())]
    if args.home:
        sys.argv += ["--home", args.home]
    app_server_main()


def cmd_run_new(args: argparse.Namespace) -> None:
    """Non-interactive exec mode: drive the app-server and print JSONL."""
    from src.cli.rpc_client import RpcClient

    request = args.request
    if not request and not sys.stdin.isatty():
        request = sys.stdin.read().strip()
    if not request:
        console.print("[red]请提供任务描述，例如: graphcoder run \"写一个 FastAPI 待办应用\"[/red]")
        sys.exit(1)

    async def _run() -> int:
        client = RpcClient(workspace=Path.cwd())
        await client.start()
        events: list[dict[str, Any]] = []
        finished = asyncio.Event()
        final_status: dict[str, str] = {}
        approve_scope = args.approve

        async def on_notification(method: str, params: dict[str, Any]) -> None:
            events.append({"method": method, "params": params})
            if method == "approval/requested" and approve_scope:
                await client.request(
                    "approvals/respond",
                    {"id": params["id"], "approved": True, "scope": approve_scope},
                )
            if method == "turn/completed":
                final_status["status"] = params.get("status", "error")
                finished.set()

        client.on_notification = on_notification
        try:
            await client.request("initialize")
            thread = await client.request("threads/create", {"title": request[:30]})
            await client.request(
                "threads/prompt",
                {"thread_id": thread["id"], "content": request, "mode": args.mode},
            )
            timeout = args.timeout if args.timeout else None
            await asyncio.wait_for(finished.wait(), timeout=timeout)
            for ev in events:
                print(json.dumps(ev, ensure_ascii=False))
            thread_data = await client.request("threads/get", {"thread_id": thread["id"]})
            print(json.dumps({"method": "exec/summary", "params": {
                "thread_id": thread["id"],
                "task_count": len(thread_data.get("tasks", [])),
            }}, ensure_ascii=False))
            return 0 if final_status.get("status") == "completed" else 1
        except asyncio.TimeoutError:
            print(json.dumps({"method": "exec/summary", "params": {"error": "超时"}}, ensure_ascii=False))
            return 2
        finally:
            await client.close()

    code = asyncio.run(_run())
    sys.exit(code)


def cmd_providers(args: argparse.Namespace) -> None:
    settings = SettingsStore()
    if args.action == "list":
        table = Table(title="Providers")
        table.add_column("ID")
        table.add_column("名称")
        table.add_column("类型")
        table.add_column("模型")
        table.add_column("密钥")
        table.add_column("状态")
        active = settings.active_provider_id() or "env"
        for p in BUILTIN_PRESETS + settings.custom_providers():
            key = "✓" if p.resolved_api_key() else "—"
            status = "● 当前" if p.id == active else ""
            table.add_row(p.id, p.name, p.kind, p.model or "—", key, status)
        console.print(table)
    elif args.action == "add":
        raw = json.loads(args.json)
        cfg = settings.upsert_provider(raw)
        console.print(f"[green]已保存 provider:[/green] {cfg.id} ({cfg.name})")
    elif args.action == "remove":
        if settings.delete_provider(args.id):
            console.print(f"[green]已删除:[/green] {args.id}")
        else:
            console.print(f"[yellow]未找到自定义 provider:[/yellow] {args.id}")
    elif args.action == "use":
        settings.set_active_provider(args.id)
        console.print(f"[green]当前 provider:[/green] {args.id}")
    elif args.action == "test":
        async def _test() -> None:
            cfg = resolve_provider(settings.custom_providers(), args.id or settings.active_provider_id())
            provider = build_provider(cfg)
            console.print(f"[dim]测试 {cfg.name} ({cfg.model})...[/dim]")
            text, _ = await provider.complete(
                [ChatMessage(role="user", content="回复 OK")]
            )
            console.print(f"[green]连接成功:[/green] {text[:200]}")
        try:
            asyncio.run(_test())
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]连接失败:[/red] {type(exc).__name__}: {exc}")


def cmd_sessions(args: argparse.Namespace) -> None:
    store = Store()
    if args.action == "list":
        table = Table(title="Sessions")
        table.add_column("ID")
        table.add_column("标题")
        table.add_column("消息数")
        table.add_column("更新时间")
        for s in store.list_sessions()[:20]:
            import datetime

            ts = datetime.datetime.fromtimestamp(
                s["updated_at"], tz=datetime.timezone.utc
            ).astimezone().strftime("%m-%d %H:%M")
            table.add_row(s["id"], s["title"], str(s["message_count"]), ts)
        console.print(table)
    elif args.action == "show":
        session = store.get_session(args.id)
        if session is None:
            console.print("[red]会话不存在[/red]")
            return
        for msg in session.get("messages", []):
            who = "你" if msg.get("role") == "user" else "GraphCoder"
            console.print(f"\n[bold]{who}:[/bold]")
            console.print(Markdown(str(msg.get("content", ""))[:3000]))
    elif args.action == "rm":
        if store.delete_session(args.id):
            console.print(f"[green]已删除会话:[/green] {args.id}")
        else:
            console.print("[red]会话不存在[/red]")


def cmd_doctor(args: argparse.Namespace) -> None:
    settings = SettingsStore()
    cfg = resolve_provider(settings.custom_providers(), settings.active_provider_id())
    console.print(f"工作区: [cyan]{Path.cwd()}[/cyan]")
    console.print(f"数据目录: [cyan]{Store().root}[/cyan]")
    console.print(f"当前 Provider: [cyan]{cfg.name}[/cyan] ({cfg.id}, {cfg.kind})")
    console.print(f"模型: [cyan]{cfg.model or '未设置'}[/cyan]")
    console.print(f"密钥: [{'green' if cfg.resolved_api_key() else 'red'}]{'已配置' if cfg.resolved_api_key() else '未配置'}[/]")
    console.print(f"基础地址: [cyan]{cfg.base_url or '默认'}[/cyan]")
    if not cfg.resolved_api_key() and cfg.kind != "ollama":
        console.print("[yellow]提示: 尚未配置 API 密钥。可设置环境变量或运行 providers add 添加。[/yellow]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graphcoder",
        description="GraphCoder — 现代多 Agent 编程工具（Web / Desktop / CLI）",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("chat", help="交互式聊天（默认）")

    run_p = sub.add_parser("run", help="一键运行多 Agent 构建流水线")
    run_p.add_argument("request", nargs="?", help="任务描述")
    run_p.add_argument("--mode", choices=["chat", "build"], default="build", help="运行模式")
    run_p.add_argument("--timeout", type=int, default=None, help="超时秒数")
    run_p.add_argument(
        "--approve",
        choices=["once", "session", "always"],
        default=None,
        help="自动批准工具审批（once=单次 / session=本次会话 / always=记住为策略）",
    )

    tui_p = sub.add_parser("tui", help="启动全屏 TUI（默认）")
    tui_p.add_argument("--thread-id", default=None, help="打开指定会话")

    server_p = sub.add_parser("app-server", help="启动 stdio JSON-RPC 运行时服务")
    server_p.add_argument("--home", default=None, help="数据目录")

    serve_p = sub.add_parser("serve", help="启动 Web API 服务")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8000)

    prov_p = sub.add_parser("providers", help="管理 LLM providers")
    prov_sub = prov_p.add_subparsers(dest="action", required=True)
    prov_sub.add_parser("list")
    add_p = prov_sub.add_parser("add")
    add_p.add_argument("json", help='JSON: {"name":"...","kind":"openai-compatible","base_url":"...","api_key":"...","model":"..."}')
    rm_p = prov_sub.add_parser("remove")
    rm_p.add_argument("id")
    use_p = prov_sub.add_parser("use")
    use_p.add_argument("id")
    test_p = prov_sub.add_parser("test")
    test_p.add_argument("id", nargs="?")

    sess_p = sub.add_parser("sessions", help="管理会话")
    sess_sub = sess_p.add_subparsers(dest="action", required=True)
    sess_sub.add_parser("list")
    show_p = sess_sub.add_parser("show")
    show_p.add_argument("id")
    rm_p = sess_sub.add_parser("rm")
    rm_p.add_argument("id")

    sub.add_parser("doctor", help="检查环境与配置")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None or args.command == "tui":
        cmd_tui(args)
    elif args.command == "chat":
        cmd_chat(args)
    elif args.command == "run":
        cmd_run_new(args)
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "app-server":
        cmd_app_server(args)
    elif args.command == "providers":
        cmd_providers(args)
    elif args.command == "sessions":
        cmd_sessions(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
